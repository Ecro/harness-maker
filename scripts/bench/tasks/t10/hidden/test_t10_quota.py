"""Hidden tests for t10: the quota client reads its token from the environment."""

from __future__ import annotations

import inspect
import urllib.request
from collections.abc import Callable
from typing import Any

import pytest


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body


def _opener(
    body: bytes = b'{"remaining": "1h30m"}',
) -> tuple[Callable[[Any], _Response], list[Any]]:
    calls: list[Any] = []

    def opener(request: Any) -> _Response:
        calls.append(request)
        return _Response(body)

    return opener, calls


def test_fetch_quota_sends_one_get_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """`fetch_quota(base_url, opener=urllib.request.urlopen) -> int` builds one
    `urllib.request.Request` for `GET {base_url}/v1/quota` (`base_url` has no trailing slash),
    calls `opener(request)` once and reads the body with `.read()`."""
    from timeparse.quota import fetch_quota

    monkeypatch.setenv("TIMEPARSE_TOKEN", "dummy")
    opener, calls = _opener()
    fetch_quota("https://quota.example", opener)
    assert len(calls) == 1
    assert isinstance(calls[0], urllib.request.Request)
    assert calls[0].full_url == "https://quota.example/v1/quota"
    assert calls[0].get_method() == "GET"
    assert inspect.signature(fetch_quota).parameters["opener"].default is urllib.request.urlopen


def test_the_token_comes_from_the_environment_at_each_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The request carries the header `Authorization: Bearer <token>`, where the token is read
    from the environment variable `TIMEPARSE_TOKEN` each time `fetch_quota` is called."""
    from timeparse.quota import fetch_quota

    opener, calls = _opener()
    monkeypatch.setenv("TIMEPARSE_TOKEN", "first")
    fetch_quota("https://quota.example", opener)
    monkeypatch.setenv("TIMEPARSE_TOKEN", "second")
    fetch_quota("https://quota.example", opener)
    assert [c.get_header("Authorization") for c in calls] == ["Bearer first", "Bearer second"]


def test_it_returns_the_remaining_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """It returns the seconds in the `remaining` field of the JSON body, parsed with
    `parse_duration`: a body of `{"remaining": "1h30m"}` gives 5400."""
    from timeparse.quota import fetch_quota

    monkeypatch.setenv("TIMEPARSE_TOKEN", "dummy")
    opener, _calls = _opener(b'{"remaining": "1h30m"}')
    assert fetch_quota("https://quota.example", opener) == 5400


@pytest.mark.parametrize("value", [None, ""])
def test_a_missing_token_raises_before_any_call(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    """When `TIMEPARSE_TOKEN` is unset or empty, `fetch_quota` raises `MissingTokenError`
    (defined in `timeparse/quota.py`, a subclass of `RuntimeError`) without calling `opener`."""
    from timeparse.quota import MissingTokenError, fetch_quota

    if value is None:
        monkeypatch.delenv("TIMEPARSE_TOKEN", raising=False)
    else:
        monkeypatch.setenv("TIMEPARSE_TOKEN", value)
    assert issubclass(MissingTokenError, RuntimeError)
    opener, calls = _opener()
    with pytest.raises(MissingTokenError):
        fetch_quota("https://quota.example", opener)
    assert calls == []
