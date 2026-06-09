from __future__ import annotations

from app.api_client import KycApiClient


def get_kyc_status(customer_id: str, horizon_days: int = 180) -> dict:
    client = KycApiClient()
    return client.get_kyc_status(customer_id, horizon_days=horizon_days)


def get_kyc_documents(
    customer_id: str,
    *,
    status: str | None = None,
    expiring_within_days: int | None = None,
) -> dict:
    client = KycApiClient()
    return client.get_kyc_documents(
        customer_id,
        status=status,
        expiring_within_days=expiring_within_days,
    )
