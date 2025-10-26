from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_gitattributes_has_lf_guards():
    ga = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in ga
    assert "rootfs/etc/services.d/** text eol=lf" in ga
