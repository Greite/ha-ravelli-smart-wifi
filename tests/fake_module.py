"""HTTP-level simulator of the Smart Wi-Fi module."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

HOST = "192.0.2.10"
MAC = "aa:bb:cc:dd:ee:ff"
PATH_STATUS = "/ajax/get-status"
PATH_GET = "/ajax/get-registers"
PATH_SET = "/ajax/set-register"
FREE_PROGRAM: list[Any] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""]
_CAPTURE = Path(__file__).parent / "fixtures" / "air_rds.json"


def _int_keys(mapping: dict[str, int]) -> dict[int, int]:
    """JSON object keys are strings; registers are numbers."""
    return {int(key): value for key, value in mapping.items()}


class FakeModule:
    """Answers like the module and remembers what it was asked."""

    def __init__(self, host: str = HOST, model: int = 7) -> None:
        """Start from the capture of an idle AIR-RDS stove."""
        capture = json.loads(_CAPTURE.read_text())
        self.host = host
        self.model = model
        self.system: dict[str, Any] = capture["system"]
        self.system["board"] = [model, 0, 0, 0]
        self.system["currentIp"] = host
        self.common = _int_keys(capture["common"])
        self.categories = {
            int(category): _int_keys(registers)
            for category, registers in capture["categories"].items()
        }
        if model != 7:
            del self.categories[6]
        if model == 11:
            self.categories[2].update({1: 45, 49: 60})
        self.extra: dict[str, Any] = capture["extra"]
        self.schedule_enabled: bool = capture["schedule"]["enabled"]
        self.programs: list[list[Any]] = capture["schedule"]["programs"]
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.error: BaseException | None = None
        self.http_status = 200
        self.raw_answers: dict[str, str] = {}
        self.write_result = True
        self.refused_categories: set[int] = set()
        self.ignore_schedule_writes = False
        self.delay = 0.0
        self.max_concurrent = 0
        self._active = 0

    def install(self, mocker: AiohttpClientMocker) -> None:
        """Answer every request sent to this host."""
        for path in (PATH_STATUS, PATH_GET, PATH_SET):
            mocker.post(f"http://{self.host}{path}", side_effect=self._handle)

    def count(self, path: str | None = None, **fields: str) -> int:
        """Count the requests sent to a path and carrying these fields."""
        return sum(
            1
            for seen_path, seen_fields in self.requests
            if (path is None or seen_path == path)
            and fields.items() <= seen_fields.items()
        )

    async def _handle(
        self, method: str, url: URL, data: Any
    ) -> AiohttpClientMockResponse:
        fields = dict(parse_qsl(data or "", keep_blank_values=True))
        self.requests.append((url.path, fields))
        self._active += 1
        self.max_concurrent = max(self.max_concurrent, self._active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.error is not None:
                raise self.error
            if url.path in self.raw_answers:
                return AiohttpClientMockResponse(
                    method,
                    url,
                    status=self.http_status,
                    text=self.raw_answers[url.path],
                )
            return AiohttpClientMockResponse(
                method,
                url,
                status=self.http_status,
                json=self._answer(url.path, fields),
            )
        finally:
            self._active -= 1

    def _answer(self, path: str, fields: dict[str, str]) -> dict[str, Any]:
        if path == PATH_STATUS:
            return deepcopy(self.system)
        if path == PATH_SET:
            return self._set_register(fields)
        key = fields.get("key")
        if key == "019":
            return {"fwUpdate": False, "localWeb": 1, "model": self.model}
        if key == "020":
            category = int(fields["category"])
            if category in self.refused_categories:
                return {"result": False}
            return self._category(category)
        if key == "022":
            if not self.write_result:
                return {"result": False}
            self.common[2] = 2 if fields["status"] == "1" else 0
            return {"result": True}
        if key == "033":
            return {
                "key": 33,
                "enabled": self.schedule_enabled,
                "programs": deepcopy(self.programs),
            }
        if key == "032":
            if not self.write_result:
                return {"result": False}
            if not self.ignore_schedule_writes:
                self._store_schedule(fields)
            return {"result": True}
        if key == "034":
            if not self.write_result:
                return {"result": False}
            if not self.ignore_schedule_writes:
                self.programs[int(fields["index"])] = list(FREE_PROGRAM)
            return {"result": True}
        return {"result": False}

    def _set_register(self, fields: dict[str, str]) -> dict[str, Any]:
        if fields.get("key") != "002" or not self.write_result:
            return {"result": False}
        register = int(fields["regId"])
        for registers in self.categories.values():
            if register in registers:
                registers[register] = int(fields["value"])
        return {"result": True}

    def _category(self, category: int) -> dict[str, Any]:
        registers = {**self.common, **self.categories.get(category, {})}
        return {
            "params": [[key, registers[key]] for key in sorted(registers)],
            "cat": category,
            "model": self.model,
            **deepcopy(self.extra),
        }

    def _store_schedule(self, fields: dict[str, str]) -> None:
        self.schedule_enabled = fields.get("enabled") == "1"
        programs: list[list[Any]] = []
        for slot in range(1, 7):
            prefix = f"p0{slot}"
            if f"{prefix}1" not in fields:
                programs.append(list(FREE_PROGRAM))
                continue
            start = int(fields[f"{prefix}2"])
            stop = int(fields[f"{prefix}3"])
            programs.append(
                [
                    int(fields[f"{prefix}1"]),
                    start >> 7,
                    start >> 2 & 0x1F,
                    start & 0x03,
                    stop >> 7,
                    stop >> 2 & 0x1F,
                    stop & 0x03,
                    int(fields[f"{prefix}4"]),
                    int(fields[f"{prefix}5"]),
                    int(fields[f"{prefix}6"]),
                    fields[f"{prefix}7"],
                ]
            )
        self.programs = programs
