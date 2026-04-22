from app.api.client import BankingApiClient


def get_transactions(customer_id: str | None = None, fraud_only: bool = False) -> list:
    client = BankingApiClient()
    params: dict[str, str | bool] = {"fraudOnly": fraud_only}
    if customer_id:
        params["customerId"] = customer_id
    return client.get("/api/banking/transactions", params=params)
