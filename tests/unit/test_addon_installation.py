import pytest


pytestmark = pytest.mark.skip(
    reason="Disabled: requires Docker or HA runtime not available in this environment."
)


def test_addon_placeholder() -> None:
    """Placeholder test to satisfy pytest collection in static environments."""
    assert True
