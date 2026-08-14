from ..models import EngineOptions


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
    work = estimate_work(engine, n_ops, n_isochromats, options.epg_kmax, n_pools)
    if work > options.max_work:
        raise ValueError(f"estimated work {work} exceeds max_work {options.max_work}")
    return work
