"""Differential test: the lease window agrees with an independent oracle.

The lease schema compares versions with a tuple-padded dotted-numeric order
(`mrqlab_agent.license._version_at_least`). `packaging.version.Version`
implements a PEP 440 total order that is independently maintained. For the ASCII
dotted versions the lease schema permits, the two orders must coincide, so any
disagreement is a defect in one of them — an oracle we did not write and cannot
"teach" the same bug.

`packaging` is already a runtime dependency of the toolchain; no new dependency.
"""
from packaging.version import InvalidVersion, Version
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mrqlab_agent.license import _version_at_least

VERSION = st.from_regex(r"[0-9]{1,4}(\.[0-9]{1,4}){0,3}", fullmatch=True)
_SETTINGS = settings(max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@_SETTINGS
@given(a=VERSION, b=VERSION)
def test_window_order_matches_packaging_version_order(a, b):
    try:
        expected = Version(a) >= Version(b)
    except InvalidVersion:  # pragma: no cover - the strategy only emits valid forms
        return
    assert _version_at_least(a, b) == expected, f"{a!r} vs {b!r}"
