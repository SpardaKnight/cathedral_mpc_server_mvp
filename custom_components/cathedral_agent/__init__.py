from __future__ import annotations
from homeassistant.core import HomeAssistant
from .conversation import CathedralConversationAgent

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    return True
