from app.api.client import BankingApiClient


def get_alerts_request_url(customer_id: str | None = None, severity: str | None = None) -> str:
    client = BankingApiClient()
    params: dict[str, str] = {}
    if customer_id:
        params["customerId"] = customer_id
    if severity:
        params["severity"] = severity
    return client.build_url("/api/banking/alerts", params=params or None)


def get_alerts(customer_id: str | None = None, severity: str | None = None) -> list:
    client = BankingApiClient()
    params: dict[str, str] = {}
    if customer_id:
        params["customerId"] = customer_id
    if severity:
        params["severity"] = severity
    return client.get("/api/banking/alerts", params=params or None)
