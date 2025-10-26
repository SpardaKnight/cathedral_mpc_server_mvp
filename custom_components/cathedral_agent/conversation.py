from __future__ import annotations

import uuid

import aiohttp
from homeassistant.components import conversation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.components.conversation import (
    AbstractConversationAgent,
    ConversationResult,
)

ORCH_URL_DEFAULT = "http://homeassistant.local:8001"


class CathedralConversationAgent(AbstractConversationAgent):
    def __init__(self, hass: HomeAssistant, base_url: str = ORCH_URL_DEFAULT):
        self.hass = hass
        self.base_url = base_url.rstrip("/")

    @property
    def attribution(self) -> dict[str, str]:
        return {"name": "Cathedral Orchestrator", "url": self.base_url}

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> ConversationResult:
        text = user_input.text or ""
        conv_id = user_input.conversation_id or str(uuid.uuid4())
        payload = {
            "model": "openai/gpt-oss-20b",
            "stream": False,
            "messages": [{"role": "user", "content": text}],
            "metadata": {"conversation_id": conv_id},
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{self.base_url}/v1/chat/completions", json=payload, timeout=60
            ) as r:
                data = await r.json()
        # OpenAI shape: choices[0].message.content
        content = ""
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            content = str(data)
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(content)
        return ConversationResult(response=response)
