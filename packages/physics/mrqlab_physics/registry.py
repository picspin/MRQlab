from importlib.metadata import entry_points

from .base import EnginePlugin, SimulationEngine
from .engines import BlochEngine, EPGEngine, HybridEngine, PdgEngine, SpectralEngine, SsepgEngine


_BUILTIN_TYPES = (BlochEngine, EPGEngine, HybridEngine, PdgEngine, SpectralEngine, SsepgEngine)
_engines: dict[str, tuple[SimulationEngine, str]] | None = None


def _legacy_engine_error(entry_name: str) -> TypeError:
    return TypeError(
        f"physics entry point {entry_name!r} must publish an EnginePlugin backend "
        "descriptor; full SimulationEngine entry points are not accepted"
    )


def _coerce_engine(candidate, entry_name: str) -> SimulationEngine:
    if isinstance(candidate, SimulationEngine) or (
        isinstance(candidate, type) and issubclass(candidate, SimulationEngine)
    ):
        raise _legacy_engine_error(entry_name)
    plugin = candidate() if isinstance(candidate, type) else candidate
    if isinstance(plugin, SimulationEngine):
        raise _legacy_engine_error(entry_name)
    if not isinstance(plugin, EnginePlugin):
        raise TypeError(
            f"physics entry point {entry_name!r} did not load an EnginePlugin "
            "backend descriptor"
        )
    if plugin.name.lower() != entry_name.lower():
        raise ValueError(
            f"physics entry point {entry_name!r} loaded plugin named {plugin.name!r}"
        )
    return SimulationEngine(plugin)


def _load_engines() -> dict[str, tuple[SimulationEngine, str]]:
    loaded = {
        engine.name: (engine, "built-in")
        for engine in (kind() for kind in _BUILTIN_TYPES)
    }
    for entry_point in entry_points(group="mrqlab.physics_engines"):
        name = entry_point.name.lower()
        if name in loaded:
            raise ValueError(f"duplicate physics engine {name!r}")
        loaded[name] = (_coerce_engine(entry_point.load(), entry_point.name), "entry-point")
    return loaded


def refresh_engines() -> None:
    global _engines
    _engines = _load_engines()


def _registry() -> dict[str, tuple[SimulationEngine, str]]:
    global _engines
    if _engines is None:
        refresh_engines()
    return _engines


def get_engine(name: str = "bloch") -> SimulationEngine:
    registry = _registry()
    try:
        return registry[name.lower()][0]
    except KeyError:
        choices = ", ".join(sorted(registry))
        raise ValueError(f"unknown engine {name!r}; choose from {choices}") from None


def list_engines() -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "available": engine.available,
            "description": engine.description,
            "source": source,
            "representation": engine.plugin.representation,
            "supports": sorted(engine.plugin.supports),
        }
        for name, (engine, source) in sorted(_registry().items())
    ]
