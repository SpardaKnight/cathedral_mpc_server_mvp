# Patch 0013 — HA Docker onnxruntime fix

- add `py3-onnxruntime` to the Alpine package list so chromadb's dependency can resolve without pip wheels
- create the venv with `--system-site-packages` to expose the system `onnxruntime` inside `/opt/venv`
- document the onnxruntime handling in the README and bump the add-on version to 0.1.2 for Supervisor rebuilds
