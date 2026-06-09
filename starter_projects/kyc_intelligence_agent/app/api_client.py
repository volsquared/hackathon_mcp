from __future__ import annotations

import os
from typing import Any

import requests


class KycApiClient:
    def __init__(self, base_url: str | None = None, timeout: int = 15) -> None:
        self.base_url = (base_url or os.getenv("DATA_API_URL") or "http://localhost:8080").rstrip("/")
        self.timeout = timeout

    def get_kyc_status(self, customer_id: str, horizon_days: int = 180) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/api/kyc/status/{customer_id}",
            params={"horizonDays": horizon_days},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", payload)

    def get_kyc_documents(
        self,
        customer_id: str,
        *,
        status: str | None = None,
        expiring_within_days: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if expiring_within_days is not None:
            params["expiringWithinDays"] = expiring_within_days

        response = requests.get(
            f"{self.base_url}/api/kyc/documents/{customer_id}",
            params=params or None,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", payload)
