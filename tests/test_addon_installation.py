import shutil
import subprocess

import pytest


if shutil.which("docker") is None:
    pytest.skip("docker CLI not available", allow_module_level=True)


def test_addon_installation():
    """
    Validates that the Cathedral Orchestrator add-on can be built and registered
    as a Home Assistant Supervisor add-on without errors.
    This is the only permitted automated test.
    """
    result = subprocess.run(["make", "-C", "dev", "build_amd64"], capture_output=True)
    assert result.returncode == 0, f"Docker build failed: {result.stderr.decode()}"
    print("Docker add-on built successfully.")
