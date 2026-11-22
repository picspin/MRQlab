"""Differential test: the lease window agrees with an independent oracle.

The lease schema compares versions with a tuple-padded dotted-numeric order
(`mrqlab_agent.license._version_at_least`). `packaging.version.Version`
implements a PEP 440 total order that is independently maintained. For the ASCII
dotted versions the lease schema permits, the two orders must coincide, so any
disagreement is a defect in one of them — an oracle we did not write and cannot
"teach" the same bug.

`packaging` and `hypothesis` are explicit development dependencies (not
transitive runtime assumptions); see `pyproject.toml`'s `dev` extra.
"""
from packaging.version import Version
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mrqlab_agent.license import _version_at_least

# PEP 440 accepts the dotted numeric domain below when each component is either
# "0" or starts non-zero. The production parser also accepts leading zeros, but
# those are deliberately covered by the direct property tests instead of being
# silently skipped by this independent oracle.
COMPONENT = st.one_of(st.just("0"), st.from_regex(r"[1-9][0-9]{0,3}", fullmatch=True))
VERSION = st.lists(COMPONENT, min_size=1, max_size=4).map(".".join)
_SETTINGS = settings(max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@_SETTINGS
@given(a=VERSION, b=VERSION)
def test_window_order_matches_packaging_version_order(a, b):
    assert _version_at_least(a, b) == (Version(a) >= Version(b)), f"{a!r} vs {b!r}"
