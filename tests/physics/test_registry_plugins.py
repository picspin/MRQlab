import pytest

from mrqlab_physics.base import SimulationEngine
from mrqlab_physics.registry import get_engine, list_engines, refresh_engines


class DemoEngine(SimulationEngine):
    name = "demo"
    description = "test plugin"

    def simulate(self, sequence, phantom, scanner, options):
        raise AssertionError("plugin smoke test does not execute simulation")


class FakeEntryPoint:
    name = "demo"
    value = "tests.fake:DemoEngine"

    def load(self):
        return DemoEngine


@pytest.fixture(autouse=True)
def restore_builtin_registry(monkeypatch):
    yield
    monkeypatch.undo()
    refresh_engines()


def test_entry_point_class_is_instantiated(monkeypatch):
    monkeypatch.setattr("mrqlab_physics.registry.entry_points", lambda group: [FakeEntryPoint()])
    refresh_engines()

    assert isinstance(get_engine("DEMO"), DemoEngine)
    descriptor = next(item for item in list_engines() if item["name"] == "demo")
    assert descriptor == {
        "name": "demo",
        "available": True,
        "description": "test plugin",
        "source": "entry-point",
    }


def test_plugin_cannot_shadow_builtin(monkeypatch):
    FakeEntryPoint.name = "bloch"
    monkeypatch.setattr("mrqlab_physics.registry.entry_points", lambda group: [FakeEntryPoint()])

    with pytest.raises(ValueError, match="duplicate physics engine 'bloch'"):
        refresh_engines()

    FakeEntryPoint.name = "demo"
