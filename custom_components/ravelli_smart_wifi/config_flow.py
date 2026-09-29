"""Config flow of the Ravelli Smart Wi-Fi integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
from ipaddress import IPv4Network, ip_address
import logging
from typing import Any

from getmac import get_mac_address
from homeassistant.components import network
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from .api import (
    WinetClient,
    WinetConnectionError,
    WinetError,
    WinetResponseError,
    is_winet_status,
    normalize_host,
)
from .const import DOMAIN, ISSUE_URL, SCAN_CONCURRENCY, SCAN_MIN_PREFIX, SCAN_TIMEOUT
from .models import SUPPORTED_MODELS, StoveModel

_LOGGER = logging.getLogger(__name__)

CHOICE_MANUAL = "manual"
# What the lookup returns on some systems when it finds nothing.
_NO_MAC = "00:00:00:00:00:00"
_MANUAL_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """A supported module found at an address."""

    host: str
    model: StoveModel
    mac: str | None


class ProbeError(Exception):
    """The address cannot be used."""

    def __init__(self, reason: str, model_code: object = None) -> None:
        """Remember the reason, which is also the translation key."""
        super().__init__(reason)
        self.reason = reason
        self.model_code = model_code


async def async_get_mac(hass: HomeAssistant, host: str) -> str | None:
    """Look the MAC address of a host up; the module does not report it."""
    try:
        ip_address(host)
    except ValueError:
        lookup = partial(get_mac_address, hostname=host)
    else:
        lookup = partial(get_mac_address, ip=host)
    mac = await hass.async_add_executor_job(lookup)
    if not mac or mac == _NO_MAC:
        return None
    return format_mac(mac)


async def async_probe(hass: HomeAssistant, host: str) -> ProbeResult:
    """Check that a supported module answers at an address."""
    client = WinetClient(async_get_clientsession(hass), host)
    try:
        status = await client.get_status()
        if not is_winet_status(status):
            raise ProbeError("not_winet")
        info = await client.get_info()
    except WinetConnectionError as err:
        raise ProbeError("cannot_connect") from err
    except WinetResponseError as err:
        raise ProbeError("not_winet") from err
    code = info.get("model")
    model = SUPPORTED_MODELS.get(code) if isinstance(code, int) else None
    if model is None:
        raise ProbeError("unsupported_model", code)
    return ProbeResult(host=host, model=model, mac=await async_get_mac(hass, host))


async def async_local_networks(hass: HomeAssistant) -> list[IPv4Network]:
    """Return the local networks that are small enough to be searched."""
    networks: list[IPv4Network] = []
    for adapter in await network.async_get_adapters(hass):
        if not adapter["enabled"]:
            continue
        for address in adapter["ipv4"]:
            if address["network_prefix"] < SCAN_MIN_PREFIX:
                continue
            found = IPv4Network(
                f"{address['address']}/{address['network_prefix']}", strict=False
            )
            if found.is_loopback or found.is_link_local or found in networks:
                continue
            networks.append(found)
    return networks


async def async_scan(hass: HomeAssistant) -> list[str]:
    """Return the addresses of the local networks where a module answers."""
    session = async_get_clientsession(hass)
    limit = asyncio.Semaphore(SCAN_CONCURRENCY)

    async def check(host: str) -> str | None:
        async with limit:
            try:
                status = await WinetClient(
                    session, host, timeout=SCAN_TIMEOUT
                ).get_status()
            except WinetError:
                return None
        return host if is_winet_status(status) else None

    hosts = [
        str(host)
        for found in await async_local_networks(hass)
        for host in found.hosts()
    ]
    return [host for host in await asyncio.gather(*map(check, hosts)) if host]


class RavelliConfigFlow(ConfigFlow, domain=DOMAIN):
    """Adds a stove from the user interface."""

    VERSION = 1

    def __init__(self) -> None:
        """Start with nothing found."""
        self._scan_task: asyncio.Task[list[str]] | None = None
        self._found: list[str] = []
        self._scan_was_empty = False
        self._probe: ProbeResult | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer the network search or the manual entry."""
        return self.async_show_menu(step_id="user", menu_options=["scan", "manual"])

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search the local networks while showing a progress screen."""
        if self._scan_task is None:
            # Not eager: the first call must return the progress screen.
            self._scan_task = self.hass.async_create_task(
                async_scan(self.hass), eager_start=False
            )
        if not self._scan_task.done():
            return self.async_show_progress(
                step_id="scan", progress_action="scan", progress_task=self._scan_task
            )
        try:
            found = self._scan_task.result()
        except Exception:
            # A failed search must not block the manual entry.
            _LOGGER.exception("The network search failed")
            found = []
        self._scan_task = None
        configured = {entry.data[CONF_HOST] for entry in self._async_current_entries()}
        self._found = [host for host in found if host not in configured]
        if not self._found:
            self._scan_was_empty = True
            return self.async_show_progress_done(next_step_id="manual")
        return self.async_show_progress_done(next_step_id="pick")

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick one of the modules found."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_HOST] == CHOICE_MANUAL:
                return await self.async_step_manual()
            result = await self._async_try(user_input[CONF_HOST], errors)
            if result is not None:
                return result
        options = [SelectOptionDict(value=host, label=host) for host in self._found]
        options.append(
            SelectOptionDict(value=CHOICE_MANUAL, label="Enter the address manually")
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.LIST,
                        translation_key="host_choice",
                    )
                )
            }
        )
        return self.async_show_form(step_id="pick", data_schema=schema, errors=errors)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the address of the module."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])
            result = await self._async_try(host, errors)
            if result is not None:
                return result
        elif self._scan_was_empty:
            self._scan_was_empty = False
            errors["base"] = "none_found"
        return self.async_show_form(
            step_id="manual", data_schema=_MANUAL_SCHEMA, errors=errors
        )

    async def _async_try(
        self, host: str, errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        """Probe an address: create the entry, abort, or fill the errors."""
        if not host:
            errors["base"] = "invalid_host"
            return None
        try:
            probe = await async_probe(self.hass, host)
        except ProbeError as err:
            if err.reason == "unsupported_model":
                return self._abort_unsupported(err)
            errors["base"] = err.reason
            return None
        return await self._async_create(probe)

    async def _async_create(self, probe: ProbeResult) -> ConfigFlowResult:
        """Create the entry unless the module is already known."""
        if probe.mac:
            await self.async_set_unique_id(probe.mac)
            self._abort_if_unique_id_configured(updates={CONF_HOST: probe.host})
        else:
            self._async_abort_entries_match({CONF_HOST: probe.host})
        return self.async_create_entry(
            title=f"Ravelli {probe.model.name}",
            data={
                CONF_HOST: probe.host,
                CONF_MODEL: probe.model.code,
                CONF_MAC: probe.mac,
            },
        )

    def _abort_unsupported(self, err: ProbeError) -> ConfigFlowResult:
        """Stop and say which model code is not supported."""
        return self.async_abort(
            reason="unsupported_model",
            description_placeholders={
                "model": str(err.model_code),
                "issue_url": ISSUE_URL,
            },
        )
