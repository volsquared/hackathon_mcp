import os
from typing import Any
from urllib.parse import urlencode

import requests


class BankingApiClient:
    def __init__(self, base_url: str | None = None, timeout: int = 15) -> None:
        self.base_url = (base_url or os.getenv("DATA_API_URL") or "http://localhost:8080").rstrip("/")
        self.timeout = timeout

    def build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = f"{self.base_url}{path}"
        if params:
            return f"{url}?{urlencode(params, doseq=True)}"
        return url

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = requests.get(
            self.build_url(path),
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", payload)
