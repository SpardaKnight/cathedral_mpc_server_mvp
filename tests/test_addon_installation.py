import pytest


pytestmark = pytest.mark.skip(
    reason="Disabled: requires Docker or HA runtime not available in this environment."
)
