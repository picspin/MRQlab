from ..models import EngineOptions


def estimate_state_work(n_ops: int, state_width: int) -> int:
    if isinstance(n_ops, bool) or isinstance(state_width, bool):
        raise TypeError("work dimensions must be strict integers")
    if not isinstance(n_ops, int) or not isinstance(state_width, int):
        raise TypeError("work dimensions must be strict integers")
    if n_ops < 0 or state_width <= 0:
        raise ValueError("operator count must be non-negative and state width positive")
    return n_ops * state_width


def enforce_state_work_limit(
    engine: str,
    n_ops: int,
    state_width: int,
    options: EngineOptions,
) -> int:
    work = estimate_state_work(n_ops, state_width)
    if work > options.max_work:
        raise ValueError(f"estimated work {work} exceeds max_work {options.max_work}")
    return work


def estimate_work(
    engine: str,
    n_ops: int,
    n_isochromats: int,
    epg_kmax: int,
    n_pools: int,
) -> int:
    if min(n_ops, n_isochromats, n_pools) < 0:
        raise ValueError("work dimensions must be non-negative")
    widths = {
        "bloch": n_isochromats,
        "epg": 3 * (2 * epg_kmax + 1),
        "spectral": n_isochromats * n_pools,
    }
    try:
        return int(n_ops * widths[engine])
    except KeyError:
        raise ValueError(f"no work model for engine {engine!r}") from None


def enforce_work_limit(
    engine: str,
    n_ops: int,
    n_isochromats: int,
    options: EngineOptions,
    n_pools: int,
) -> int:
    widths = {
        "bloch": n_isochromats,
        "epg": 3 * (2 * options.epg_kmax + 1),
        "spectral": n_isochromats * n_pools,
    }
    try:
        state_width = widths[engine]
    except KeyError:
        raise ValueError(f"no work model for engine {engine!r}") from None
    return enforce_state_work_limit(engine, n_ops, state_width, options)
