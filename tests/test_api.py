"""Tests for the HTTP client."""

import logging

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.ravelli_smart_wifi.api import (
    WinetClient,
    WinetConnectionError,
    WinetResponseError,
    is_winet_status,
    normalize_host,
)

from .fake_module import HOST, PATH_GET, PATH_SET, PATH_STATUS, FakeModule


@pytest.fixture
def client(hass: HomeAssistant, fake_module: FakeModule) -> WinetClient:
    """Return a client that talks to the simulated module."""
    return WinetClient(async_get_clientsession(hass), HOST)


async def test_body_is_form_encoded_under_a_json_header(
    client: WinetClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """The module refuses a JSON body although it asks for the JSON header."""
    await client.get_registers(2)

    method, url, data, headers = aioclient_mock.mock_calls[-1]
    assert method.lower() == "post"
    assert str(url) == f"http://{HOST}{PATH_GET}"
    assert data == "key=020&category=2"
    assert headers["Content-Type"] == "application/json; charset=utf-8"


async def test_status_has_no_body(
    client: WinetClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """The system status is a bare POST."""
    status = await client.get_status()

    assert status["fwVer"] == "0.51"
    assert status["rssi"] == -74
    assert aioclient_mock.mock_calls[-1][2] is None
    assert str(aioclient_mock.mock_calls[-1][1]) == f"http://{HOST}{PATH_STATUS}"


async def test_reads(client: WinetClient, fake_module: FakeModule) -> None:
    """Every read returns the decoded JSON object."""
    assert (await client.get_info())["model"] == 7
    assert [50, 22] in (await client.get_registers(2))["params"]
    assert (await client.get_schedule())["programs"][0][10] == "Evening"
    assert fake_module.count(PATH_GET, key="019") == 1
    assert fake_module.count(PATH_GET, key="033") == 1


async def test_set_register(
    client: WinetClient,
    fake_module: FakeModule,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A register write carries the five fields the vendor UI sends."""
    await client.set_register(50, 23)

    assert aioclient_mock.mock_calls[-1][2] == (
        "key=002&memory=1&regId=50&value=23&result=false"
    )
    assert str(aioclient_mock.mock_calls[-1][1]) == f"http://{HOST}{PATH_SET}"
    assert fake_module.categories[2][50] == 23


async def test_refused_register_write(
    client: WinetClient, fake_module: FakeModule
) -> None:
    """The module answers result false when it refuses."""
    fake_module.write_result = False

    with pytest.raises(WinetResponseError):
        await client.set_register(50, 23)


async def test_register_write_needs_a_positive_answer(
    client: WinetClient, fake_module: FakeModule
) -> None:
    """An answer without a result is not a confirmation."""
    fake_module.raw_answers[PATH_SET] = "{}"

    with pytest.raises(WinetResponseError):
        await client.set_register(50, 23)


@pytest.mark.parametrize(
    ("on", "body"), [(True, "key=022&status=1"), (False, "key=022&status=0")]
)
async def test_set_power(
    client: WinetClient,
    aioclient_mock: AiohttpClientMocker,
    on: bool,
    body: str,
) -> None:
    """On and off go through the read endpoint with key 022."""
    await client.set_power(on)

    assert aioclient_mock.mock_calls[-1][2] == body
    assert str(aioclient_mock.mock_calls[-1][1]) == f"http://{HOST}{PATH_GET}"


async def test_schedule_write_encodes_separators_in_names(
    client: WinetClient,
    fake_module: FakeModule,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An ampersand in a name must not split the body."""
    await client.set_schedule(
        {
            "enabled": 1,
            "p011": 1,
            "p012": 200,
            "p013": 218,
            "p014": 22,
            "p015": 1,
            "p016": 127,
            "p017": "A & B = C",
        }
    )

    assert aioclient_mock.mock_calls[-1][2] == (
        "enabled=1&p011=1&p012=200&p013=218&p014=22&p015=1&p016=127"
        "&p017=A+%26+B+%3D+C&key=032"
    )
    assert fake_module.programs[0] == [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "A & B = C"]
    assert fake_module.programs[1][10] == ""


async def test_delete_program(
    client: WinetClient,
    fake_module: FakeModule,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Programs are deleted by index, starting at 0."""
    await client.delete_program(0)

    assert aioclient_mock.mock_calls[-1][2] == "key=034&index=0"
    assert fake_module.programs[0][10] == ""


@pytest.mark.parametrize(
    "error", [aiohttp.ClientConnectionError(), TimeoutError(), aiohttp.ClientOSError()]
)
async def test_unreachable_module(
    client: WinetClient, fake_module: FakeModule, error: BaseException
) -> None:
    """Network failures become one error type."""
    fake_module.error = error

    with pytest.raises(WinetConnectionError):
        await client.get_registers(2)


async def test_http_error(client: WinetClient, fake_module: FakeModule) -> None:
    """An HTTP error means the answer cannot be trusted."""
    fake_module.http_status = 500

    with pytest.raises(WinetResponseError):
        await client.get_registers(2)


@pytest.mark.parametrize(
    "answer",
    ["<html><body>Login</body></html>", "", "[]", '"text"', '{"result": false}'],
)
async def test_unexpected_answers(
    client: WinetClient, fake_module: FakeModule, answer: str
) -> None:
    """Another device at the same address must not crash the client."""
    fake_module.raw_answers[PATH_GET] = answer

    with pytest.raises(WinetResponseError):
        await client.get_registers(2)


async def test_answers_are_logged_without_the_address(
    client: WinetClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Debug logging shows what the module answered, not where it lives."""
    caplog.set_level(logging.DEBUG, logger="custom_components.ravelli_smart_wifi")

    await client.set_power(True)

    records = [r.getMessage() for r in caplog.records if PATH_GET in r.getMessage()]
    assert len(records) == 1
    assert "200" in records[0]
    assert '{"result":true}' in records[0]
    assert HOST not in caplog.text


async def test_status_answer_is_not_logged(
    client: WinetClient, caplog: pytest.LogCaptureFixture
) -> None:
    """The system status holds the address and the network name."""
    caplog.set_level(logging.DEBUG, logger="custom_components.ravelli_smart_wifi")

    await client.get_status()

    assert PATH_STATUS in caplog.text
    assert HOST not in caplog.text
    assert "example-network" not in caplog.text


@pytest.mark.parametrize(
    ("typed", "host"),
    [
        ("192.0.2.10", "192.0.2.10"),
        ("  192.0.2.10  ", "192.0.2.10"),
        ("http://192.0.2.10", "192.0.2.10"),
        ("http://192.0.2.10/", "192.0.2.10"),
        ("HTTP://192.0.2.10/management.html", "192.0.2.10"),
        ("https://stove.example/", "stove.example"),
        ("stove.example", "stove.example"),
        ("", ""),
        ("http://", ""),
    ],
)
def test_normalize_host(typed: str, host: str) -> None:
    """People paste what their browser shows."""
    assert normalize_host(typed) == host


def test_status_signature() -> None:
    """A module is recognized by two fields of its system status."""
    assert is_winet_status({"fwVer": "0.51", "board": [7, 0, 0, 0]}) is True
    assert is_winet_status({"fwVer": "0.51"}) is False
    assert is_winet_status({"board": [7, 0, 0, 0]}) is False
    assert is_winet_status({}) is False
