from app.api.client import BankingApiClient


def get_spending_summary_request_url(customer_id: str, group_by: str) -> str:
    client = BankingApiClient()
    return client.build_url(
        "/api/banking/spending-summary",
        params={"customerId": customer_id, "groupBy": group_by},
    )


def get_spending_summary(customer_id: str, group_by: str) -> dict:
    client = BankingApiClient()
    return client.get(
        "/api/banking/spending-summary",
        params={"customerId": customer_id, "groupBy": group_by},
    )
