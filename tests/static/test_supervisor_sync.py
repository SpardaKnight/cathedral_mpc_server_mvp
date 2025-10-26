import re, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "cathedral_orchestrator"
MANIFEST = ADDON / "config.yaml"
CHANGELOG = ADDON / "CHANGELOG.md"

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def _yaml_value(text: str, key: str, default=None):
    # minimal, dependency-free extractor for 'key: value' lines
    m = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*['\"]?([^'\"\n]+)", text)
    return m.group(1).strip() if m else default

def test_manifest_has_version_and_init_and_no_host_pid():
    t = _read(MANIFEST)
    ver = _yaml_value(t, "version")
    assert ver and re.match(r"^\d+\.\d+\.\d+$", ver), "config.yaml must contain semver version"
    assert re.search(r"(?m)^\s*init\s*:\s*false\b", t), "init:false is required for s6 v3"
    assert not re.search(r"(?m)^\s*host_pid\s*:\s*true\b", t), "host_pid:true is incompatible with s6 v3"

def test_changelog_top_matches_manifest_version():
    man_ver = _yaml_value(_read(MANIFEST), "version")
    m = re.search(r"(?m)^\s*##\s*\[\s*([0-9]+\.[0-9]+\.[0-9]+)\s*\]", _read(CHANGELOG))
    assert m, "CHANGELOG must have a '## [x.y.z]' entry"
    top = m.group(1)
    assert top == man_ver, f"CHANGELOG top entry {top} must match manifest version {man_ver}"

def test_single_manifest_filename_in_repo():
    others = [p for p in ROOT.rglob("config.yaml") if p != MANIFEST]
    assert not others, f"Do not ship any other 'config.yaml' files: {others}"
