# Patch 0012: PEP 668-compliant HA Docker build adjustments

- Ensured the Home Assistant add-on Dockerfile installs runtime dependencies via `python -m pip` inside `/opt/venv` after exporting the virtualenv `PATH`, matching Supervisor PEP 668 expectations.
- Removed the stray duplicate `ARG BUILD_FROM` declaration without a default while preserving the original base image value.
- Bumped the add-on manifest version to `0.1.1` so Supervisor refreshes cached layers and rebuilt with the updated Dockerfile.
- Documented the Dockerfile's use of the Home Assistant base image and isolated virtual environment for clarity in the README.
- Per repository policy, documentation-only change aside from config/container adjustments; tests and linters were not run per direct instruction.
