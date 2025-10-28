"""Shared exports for the Cathedral Orchestrator package."""

from __future__ import annotations

import asyncio
import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Dict, Optional

try:  # optional, guarded at runtime
    import yaml  # type: ignore[import]
except Exception:  # pragma: no cover - optional dependency guard
    yaml = None  # type: ignore[assignment]

from .logging_config import jlog

logger = logging.getLogger("cathedral")

if yaml is None:  # pragma: no cover - import guard
    jlog(logger, level="WARN", event="persona_yaml_module_missing")


def load_yaml(path: Path) -> Dict[str, object]:
    """Load persona configuration with graceful fallback when PyYAML is absent."""

    if yaml is None:
        try:
            with path.open("r", encoding="utf-8") as handle:
                contents = handle.read()
        except Exception as exc:  # pragma: no cover - filesystem guard
            jlog(
                logger,
                level="ERROR",
                event="persona_load_failed",
                path=str(path),
                error=str(exc),
            )
            return {}

        if not contents.strip():
            jlog(logger, level="WARN", event="persona_load_empty", path=str(path))
            return {}

        try:
            data = json.loads(contents)
        except Exception as exc:  # pragma: no cover - JSON guard
            jlog(
                logger,
                level="ERROR",
                event="persona_load_failed",
                path=str(path),
                error=str(exc),
            )
            return {}

        if isinstance(data, dict):
            jlog(
                logger,
                level="WARN",
                event="persona_load_json_fallback",
                path=str(path),
            )
            return data

        jlog(
            logger,
            level="WARN",
            event="persona_load_json_ignored",
            path=str(path),
        )
        return {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
    except Exception as exc:  # pragma: no cover - YAML guard
        jlog(
            logger,
            level="ERROR",
            event="persona_load_failed",
            path=str(path),
            error=str(exc),
        )
        return {}

    if isinstance(payload, dict):
        return payload

    jlog(logger, level="WARN", event="persona_load_yaml_non_mapping", path=str(path))
    return {}

PERSONAS_DIR = Path("/data/personas")
VOICE_HOST = "127.0.0.1"
VOICE_PORT = 8181


class PersonaManager:
    """Load persona templates from disk and track mutable runtime state."""

    def __init__(self) -> None:
        self.personas: Dict[str, Dict[str, object]] = {}
        self.active_states: Dict[str, Dict[str, object]] = {}
        self.reload()

    def reload(self) -> None:
        self.personas.clear()
        self.active_states.clear()
        if PERSONAS_DIR.is_dir():
            for entry in sorted(PERSONAS_DIR.iterdir()):
                if entry.suffix.lower() not in {".yaml", ".yml", ".json"}:
                    continue
                data = load_yaml(entry)
                if isinstance(data, dict):
                    key = entry.stem
                    self.personas[key] = data
                    self.active_states[key] = deepcopy(data)
                    jlog(
                        logger,
                        event="persona_loaded",
                        persona_id=key,
                        path=str(entry),
                    )

        if "default" not in self.personas:
            default_payload: Dict[str, object] = {
                "name": "default",
                "system_prompt": "",
                "profile": {},
            }
            self.personas["default"] = default_payload
            self.active_states["default"] = deepcopy(default_payload)
            jlog(logger, event="persona_default_seeded")

    def list_personas(self) -> Dict[str, Dict[str, object]]:
        return dict(self.personas)

    def get(self, persona_id: str, *, original: bool = False) -> Optional[Dict[str, object]]:
        store = self.personas if original else self.active_states
        persona = store.get(persona_id)
        if persona is None and persona_id != "default":
            persona = store.get("default")
        return deepcopy(persona) if isinstance(persona, dict) else None

    def reset(self, persona_id: str) -> bool:
        if persona_id not in self.personas:
            jlog(logger, level="WARN", event="persona_reset_missing", persona_id=persona_id)
            return False
        self.active_states[persona_id] = deepcopy(self.personas[persona_id])
        jlog(logger, event="persona_reset", persona_id=persona_id)
        return True


class VoiceProxy:
    """Minimal TCP proxy for Wyoming-compatible TTS services."""

    def __init__(self, host: str = VOICE_HOST, port: int = VOICE_PORT) -> None:
        self.host = host
        self.port = port

    async def synthesize(self, text: str) -> bytes:
        payload = (text or "").encode("utf-8")
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
        except Exception as exc:  # pragma: no cover - network guard
            jlog(
                logger,
                level="ERROR",
                event="voice_proxy_connect_failed",
                host=self.host,
                port=self.port,
                error=str(exc),
            )
            return b""

        try:
            writer.write(len(payload).to_bytes(4, "little") + payload)
            await writer.drain()
            chunks = []
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            audio = b"".join(chunks)
            jlog(
                logger,
                event="voice_proxy_synthesized",
                bytes=len(audio),
                host=self.host,
                port=self.port,
            )
            return audio
        except Exception as exc:  # pragma: no cover - network guard
            jlog(
                logger,
                level="ERROR",
                event="voice_proxy_synthesize_failed",
                error=str(exc),
            )
            return b""
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # pragma: no cover - cleanup guard
                pass


default_persona_manager = PersonaManager()
persona_manager = default_persona_manager
voice_proxy = VoiceProxy()

__all__ = [
    "PERSONAS_DIR",
    "PersonaManager",
    "VoiceProxy",
    "persona_manager",
    "voice_proxy",
]
