from ..models import Isochromat, Phantom, ScannerModel
from .bloch import BlochBackend


GAMMA_HZ_PER_T = 42_577_478.518


def spectral_state_width(phantom: Phantom) -> int:
    if not phantom.pools:
        raise ValueError("spectral engine requires at least one spectral pool")
    if sum(pool.fraction for pool in phantom.pools) <= 0:
        raise ValueError("spectral pool fractions must sum to a positive value")
    return len(phantom.resolved_isochromats()) * len(phantom.pools)


def spectral_isochromats(phantom: Phantom, scanner: ScannerModel) -> tuple[Isochromat, ...]:
    spectral_state_width(phantom)

    expanded: list[Isochromat] = []
    for base in phantom.resolved_isochromats():
        for pool in phantom.pools:
            expanded.append(Isochromat(
                t1=pool.t1,
                t2=pool.t2,
                proton_density=base.proton_density,
                off_resonance_hz=(
                    base.off_resonance_hz
                    + pool.chemical_shift_ppm * 1e-6 * GAMMA_HZ_PER_T * scanner.b0_t
                ),
                position_m=base.position_m,
                weight=base.weight * pool.fraction,
            ))
    return tuple(expanded)


class SpectralBackend(BlochBackend):
    def __init__(self, phantom: Phantom, scanner: ScannerModel):
        super().__init__(spectral_isochromats(phantom, scanner), scanner)
