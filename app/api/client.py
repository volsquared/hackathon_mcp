import os
from typing import Any

import requests


class BankingApiClient:
    def __init__(self, base_url: str | None = None, timeout: int = 15) -> None:
        self.base_url = (base_url or os.getenv("DATA_API_URL") or "http://localhost:8080").rstrip("/")
        self.timeout = timeout

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = requests.get(
            f"{self.base_url}{path}",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", payload)
