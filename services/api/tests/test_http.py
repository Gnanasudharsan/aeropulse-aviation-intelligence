from __future__ import annotations

import httpx
import pytest
import respx

from app.ingestion.http import FetchError, fetch_text

URL = "https://example.test/feed"


@respx.mock
async def test_retries_on_503_then_succeeds() -> None:
    route = respx.get(URL).mock(side_effect=[httpx.Response(503), httpx.Response(200, text="ok")])
    async with httpx.AsyncClient() as client:
        res = await fetch_text(client, URL, max_retries=2, base_delay=0)
    assert res.text == "ok" and route.call_count == 2
    assert len(res.checksum) == 64


@respx.mock
async def test_timeout_exhausts_retries() -> None:
    route = respx.get(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    async with httpx.AsyncClient() as client:
        with pytest.raises(FetchError) as err:
            await fetch_text(client, URL, max_retries=2, base_delay=0)
    assert route.call_count == 3
    assert "ReadTimeout" in str(err.value)


@respx.mock
async def test_404_is_not_retried() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        with pytest.raises(FetchError) as err:
            await fetch_text(client, URL, max_retries=3, base_delay=0)
    assert route.call_count == 1 and err.value.status == 404


@respx.mock
async def test_persistent_503_surfaces_status() -> None:
    respx.get(URL).mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient() as client:
        with pytest.raises(FetchError) as err:
            await fetch_text(client, URL, max_retries=1, base_delay=0)
    assert err.value.status == 503
