"""HTTP client of the Smart Wi-Fi module.

This module imports nothing from Home Assistant.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any
from urllib.parse import urlencode

import aiohttp

PATH_STATUS = "/ajax/get-status"
PATH_GET = "/ajax/get-registers"
PATH_SET = "/ajax/set-register"

# The module wants this header and a form-urlencoded body.
_HEADERS = {"Content-Type": "application/json; charset=utf-8"}


class WinetError(Exception):
    """Base class of the client errors."""


class WinetConnectionError(WinetError):
    """The module cannot be reached."""


class WinetResponseError(WinetError):
    """The module answered, but not with what was expected."""


def normalize_host(value: str) -> str:
    """Strip the scheme, the path and the spaces of a typed address."""
    host = value.strip()
    if "://" in host:
        host = host.split("://", 1)[1]
    return host.split("/", 1)[0].strip()


def is_winet_status(payload: Mapping[str, Any]) -> bool:
    """Tell whether a system status comes from a Smart Wi-Fi module."""
    return "fwVer" in payload and "board" in payload


class WinetClient:
    """Talks to one module."""

    def __init__(
        self, session: aiohttp.ClientSession, host: str, *, timeout: float = 10.0
    ) -> None:
        """Remember the session and the address."""
        self.host = host
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def _post(
        self, path: str, fields: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        body = urlencode(fields) if fields else None
        try:
            async with self._session.post(
                f"http://{self.host}{path}",
                data=body,
                headers=_HEADERS,
                timeout=self._timeout,
            ) as response:
                status = response.status
                raw = await response.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise WinetConnectionError(f"no answer from {path}") from err
        if status != 200:
            raise WinetResponseError(f"HTTP {status} from {path}")
        try:
            payload = json.loads(raw)
        except ValueError as err:
            raise WinetResponseError(f"the answer from {path} is not JSON") from err
        if not isinstance(payload, dict):
            raise WinetResponseError(f"the answer from {path} is not an object")
        if payload.get("result") is False:
            raise WinetResponseError(f"the module refused the request to {path}")
        return payload

    async def get_status(self) -> dict[str, Any]:
        """Read the system status: firmware, signal, network."""
        return await self._post(PATH_STATUS)

    async def get_info(self) -> dict[str, Any]:
        """Read the board model."""
        return await self._post(PATH_GET, {"key": "019"})

    async def get_registers(self, category: int) -> dict[str, Any]:
        """Read one register category."""
        return await self._post(PATH_GET, {"key": "020", "category": category})

    async def set_register(self, register: int, value: int) -> None:
        """Write one register."""
        payload = await self._post(
            PATH_SET,
            {
                "key": "002",
                "memory": 1,
                "regId": register,
                "value": value,
                "result": "false",
            },
        )
        if payload.get("result") is not True:
            raise WinetResponseError("the module did not confirm the write")

    async def set_power(self, on: bool) -> None:
        """Turn the stove on or off."""
        await self._post(PATH_GET, {"key": "022", "status": int(on)})

    async def get_schedule(self) -> dict[str, Any]:
        """Read the six programs and the global switch."""
        return await self._post(PATH_GET, {"key": "033"})

    async def set_schedule(self, fields: Mapping[str, int | str]) -> None:
        """Write the whole schedule table."""
        await self._post(PATH_GET, {**fields, "key": "032"})

    async def delete_program(self, index: int) -> None:
        """Free one program slot, 0 to 5."""
        await self._post(PATH_GET, {"key": "034", "index": index})
