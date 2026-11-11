"""Polite async HTTP fetching with bounded retries and exponential backoff."""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import random
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    """Upstream could not be fetched after retries."""

    def __init__(self, message: str, *, status: int | None = None, url: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.url = url


@dataclass(frozen=True, slots=True)
class FetchResult:
    url: str
    status: int
    content_type: str | None
    text: str
    fetched_at: dt.datetime
    last_modified: dt.datetime | None

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()


def build_client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(
        timeout=httpx.Timeout(s.http_timeout_seconds, connect=10.0),
        headers={"User-Agent": s.http_user_agent, "Accept-Encoding": "gzip"},
        follow_redirects=True,
    )


async def fetch_text(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, str] | None = None,
    max_retries: int | None = None,
    base_delay: float | None = None,
) -> FetchResult:
    s = get_settings()
    retries = s.http_max_retries if max_retries is None else max_retries
    base_delay = s.http_retry_base_delay if base_delay is None else base_delay
    last_exc: Exception | None = None
    last_status: int | None = None
    for attempt in range(retries + 1):
        try:
            resp = await client.get(url, params=params)
            last_status = resp.status_code
            if resp.status_code in RETRYABLE_STATUS and attempt < retries:
                delay = _retry_after(resp) or base_delay * 2**attempt + random.uniform(0, 0.5)
                log.warning("upstream_retry", url=url, status=resp.status_code, delay=delay)
                await asyncio.sleep(delay)
                continue
            if resp.status_code >= 400:
                raise FetchError(
                    f"HTTP {resp.status_code} from {url}", status=resp.status_code, url=url
                )
            lm = resp.headers.get("last-modified")
            return FetchResult(
                url=str(resp.url),
                status=resp.status_code,
                content_type=resp.headers.get("content-type"),
                text=resp.text,
                fetched_at=dt.datetime.now(dt.UTC),
                last_modified=_parse_http_date(lm),
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            if attempt < retries:
                delay = base_delay * 2**attempt + random.uniform(0, 0.5)
                log.warning(
                    "upstream_transport_retry", url=url, error=type(exc).__name__, delay=delay
                )
                await asyncio.sleep(delay)
                continue
    msg = (
        f"{type(last_exc).__name__} fetching {url}"
        if last_exc
        else f"HTTP {last_status} from {url}"
    )
    raise FetchError(msg, status=last_status, url=url) from last_exc


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("retry-after")
    if value and value.isdigit():
        return min(float(value), 60.0)
    return None


def _parse_http_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(dt.UTC)
    except (TypeError, ValueError):
        return None
