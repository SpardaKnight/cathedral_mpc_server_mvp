from __future__ import annotations
import logging
from homeassistant.core import HomeAssistant
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    return True
