import pytest

from mrqlab_sequence import Channel, Event, SequenceIR
from mrqlab_physics import EngineOptions, Phantom, ScannerModel
import mrqlab_physics.base as physics_base
from mrqlab_physics.base import SimulationEngine
from mrqlab_physics.registry import get_engine, list_engines, refresh_engines


class DemoBackend:
    def __init__(self):
        self.applied = []

    def apply(self, op):
        self.applied.append(op)

    def observe(self):
        return 1.0 + 0.0j

    def snapshot(self):
        raise AssertionError("demo plugin does not publish snapshots")


def demo_plugin(factory=None):
    make_backend = factory or (lambda phantom, scanner, options: DemoBackend())
    return physics_base.EnginePlugin(
        name="demo",
        description="test plugin",
        state_width=lambda phantom, scanner, options: 2,
        backend_factory=make_backend,
        metadata_factory=lambda phantom, scanner, options: {"plugin_marker": "core"},
    )


class LegacyFullEngine(SimulationEngine):
    name = "legacy"
    description = "obsolete full-engine plugin"

    def __init__(self):
        pass

    def simulate(self, sequence, phantom, scanner, options):
        raise AssertionError("legacy plugin must not run")


class FakeEntryPoint:
    value = "tests.fake:plugin"

    def __init__(self, candidate=demo_plugin, name="demo"):
        self.candidate = candidate
        self.name = name

    def load(self):
        return self.candidate() if self.candidate is demo_plugin else self.candidate


@pytest.fixture(autouse=True)
def restore_builtin_registry(monkeypatch):
    yield
    monkeypatch.undo()
    refresh_engines()


def test_entry_point_descriptor_is_wrapped_by_kernel_engine(monkeypatch):
    monkeypatch.setattr("mrqlab_physics.registry.entry_points", lambda group: [FakeEntryPoint()])
    refresh_engines()

    assert isinstance(get_engine("DEMO"), SimulationEngine)
    descriptor = next(item for item in list_engines() if item["name"] == "demo")
    assert descriptor == {
        "name": "demo",
        "available": True,
        "description": "test plugin",
        "source": "entry-point",
        "representation": "bloch",
        "supports": [],
    }


def test_plugin_cannot_shadow_builtin(monkeypatch):
    monkeypatch.setattr(
        "mrqlab_physics.registry.entry_points",
        lambda group: [FakeEntryPoint(name="bloch")],
    )

    with pytest.raises(ValueError, match="duplicate physics engine 'bloch'"):
        refresh_engines()


def test_kernel_rejects_plugin_work_before_backend_factory_runs():
    created = []

    def factory(phantom, scanner, options):
        created.append(True)
        return DemoBackend()

    engine = SimulationEngine(demo_plugin(factory))
    sequence = SequenceIR(name="empty", duration=0.01, channels=[])

    with pytest.raises(ValueError, match="estimated work"):
        engine.simulate(
            sequence,
            Phantom(),
            ScannerModel(),
            EngineOptions(max_work=1),
        )
    assert created == []


def test_kernel_owns_plugin_adc_nco_and_common_result_assembly():
    backends = []

    def factory(phantom, scanner, options):
        backend = DemoBackend()
        backends.append(backend)
        return backend

    sequence = SequenceIR(
        name="plugin-nco",
        duration=0.251,
        channels=[
            Channel(
                name="adc_gate",
                events=[Event(time=0.25, value=1.0), Event(time=0.251, value=0.0)],
            ),
            Channel(name="nco_freq", events=[Event(time=0.0, value=1.0)]),
        ],
    )

    result = SimulationEngine(demo_plugin(factory)).simulate(
        sequence,
        Phantom(),
        ScannerModel(),
        EngineOptions(max_work=100),
    )

    assert result.signal.tolist() == pytest.approx([-1j])
    assert result.k_trajectory.tolist() == [[0.0, 0.0, 0.0]]
    assert result.magnetization is None
    assert result.configurations is None
    assert result.meta["engine"] == "demo"
    assert result.meta["samples"] == 1
    assert result.meta["n_ops"] == 5
    assert result.meta["estimated_work"] == 10
    assert result.meta["plugin_marker"] == "core"
    assert {type(op).__name__ for op in backends[0].applied} >= {
        "Relax",
        "GradInterval",
    }
    assert not any(type(op).__name__ == "AdcSample" for op in backends[0].applied)


def test_registry_rejects_legacy_full_engine_entry_points(monkeypatch):
    monkeypatch.setattr(
        "mrqlab_physics.registry.entry_points",
        lambda group: [FakeEntryPoint(candidate=LegacyFullEngine, name="legacy")],
    )

    with pytest.raises(TypeError, match="backend descriptor.*full SimulationEngine"):
        refresh_engines()
