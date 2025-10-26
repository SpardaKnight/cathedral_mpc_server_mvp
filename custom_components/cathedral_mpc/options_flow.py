from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_ORCH_URL, DOMAIN


class CathedralConfigFlow(config_entries.ConfigFlow):
    domain = DOMAIN

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            base_url = user_input["base_url"]
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(f"{base_url.rstrip('/')}/health", timeout=10) as r:
                        if r.status != 200:
                            errors["base_url"] = "cannot_connect"
                        else:
                            return self.async_create_entry(
                                title="Cathedral MPC", data={"base_url": base_url}
                            )
            except Exception:
                errors["base_url"] = "cannot_connect"
        schema = vol.Schema({vol.Required("base_url", default=DEFAULT_ORCH_URL): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CathedralOptionsFlow(config_entry)


class CathedralOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry) -> None:
        self.config_entry = entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_options(user_input)

    async def async_step_options(self, user_input=None):
        errors = {}
        base_url = self.config_entry.data.get("base_url")
        if user_input is not None:
            # Hot-apply options to orchestrator and persist elsewhere as desired
            async with aiohttp.ClientSession() as s:
                await s.post(f"{base_url.rstrip('/')}/api/options", json=user_input)
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema(
            {
                vol.Optional("temperature", default=0.7): float,
                vol.Optional("top_p", default=0.9): float,
                vol.Optional("route_assist", default=True): bool,
            }
        )
        return self.async_show_form(
            step_id="options", data_schema=schema, errors=errors
        )
