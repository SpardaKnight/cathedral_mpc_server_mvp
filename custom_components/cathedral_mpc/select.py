from __future__ import annotations
from homeassistant.components.select import SelectEntity  # noqa: F401
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo  # noqa: F401
from .const import DOMAIN  # noqa: F401


async def async_setup_entry(hass: HomeAssistant, entry, add_entities):
    # Minimal example: not populating selects in MVP; Coordinator/OptionsFlow handle runtime
    return
