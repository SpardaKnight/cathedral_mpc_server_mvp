import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "cathedral_orchestrator"
DOCKERFILE = ADDON / "Dockerfile"
RUN = ADDON / "rootfs" / "etc" / "services.d" / "cathedral" / "run"
FINISH = ADDON / "rootfs" / "etc" / "services.d" / "cathedral" / "finish"
START = ADDON / "rootfs" / "opt" / "app" / "start.sh"

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def test_dockerfile_uses_build_from_and_no_entrypoint_or_cmd():
    text = _read(DOCKERFILE)
    assert "ARG BUILD_FROM" in text and "FROM $BUILD_FROM" in text, "Dockerfile must start from HA base via BUILD_FROM"
    assert not re.search(r"(?i)^\s*ENTRYPOINT\b", text, re.M), "Do not override HA base entrypoint (/init)"
    assert not re.search(r"(?i)^\s*CMD\b", text, re.M), "Do not set CMD; s6 manages process launch"

def test_run_is_minimal_and_executes_start():
    t = _read(RUN).strip()
    assert t.splitlines()[0].strip() == "#!/command/execlineb -P", "run must use execlineb"
    assert "with-contenv" in t, "run must include with-contenv"
    assert "exec /opt/app/start.sh" in t, "run must exec start.sh"

def test_finish_halts_container_orderly():
    t = _read(FINISH).strip()
    assert "/run/s6/basedir/bin/halt" in t, "finish must call s6 halt path"

def test_start_sh_execs_uvicorn_with_app_dir():
    t = _read(START)
    assert "cd /opt/app" in t and "--app-dir /opt/app" in t, "start.sh must set working dir and app-dir"
    assert "exec uvicorn" in t and "orchestrator.main:app" in t, "start.sh must exec uvicorn with app module"
