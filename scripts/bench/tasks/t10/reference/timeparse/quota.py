"""A small client for the quota service."""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from typing import Any

from timeparse.parse import parse_duration

TOKEN_VARIABLE = "TIMEPARSE_TOKEN"


class MissingTokenError(RuntimeError):
    """TIMEPARSE_TOKEN is unset or empty."""


def fetch_quota(
    base_url: str, opener: Callable[[urllib.request.Request], Any] = urllib.request.urlopen
) -> int:
    """Return the seconds of quota left, as reported by `GET {base_url}/v1/quota`."""
    token = os.environ.get(TOKEN_VARIABLE, "")
    if not token:
        raise MissingTokenError(f"set {TOKEN_VARIABLE} to call the quota service")
    request = urllib.request.Request(
        f"{base_url}/v1/quota", headers={"Authorization": f"Bearer {token}"}, method="GET"
    )
    body = json.loads(opener(request).read())
    return parse_duration(body["remaining"])
