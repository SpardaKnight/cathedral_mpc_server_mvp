from __future__ import annotations

import aiohttp
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from .const import DOMAIN


class CathedralCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, base_url: str):
        self._base = base_url.rstrip("/")
        super().__init__(
            hass,
            hass.helpers.logger.getLogger(DOMAIN),
            name="Cathedral MPC Coordinator",
            update_interval=timedelta(seconds=10),
        )

    async def _async_update_data(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self._base}/api/status", timeout=10) as r:
                if r.status != 200:
                    raise UpdateFailed(await r.text())
                return await r.json()
