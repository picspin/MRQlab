from .engines import BlochEngine, EPGEngine, SpectralEngine
_ENGINES = {e.name: e for e in (BlochEngine(), EPGEngine(), SpectralEngine())}
def get_engine(name: str = "bloch"):
    try: return _ENGINES[name.lower()]
    except KeyError: raise ValueError(f"unknown engine {name!r}; choose from {', '.join(_ENGINES)}") from None
def list_engines(): return [{"name": n, "available": n == "bloch"} for n in _ENGINES]
