from app.api.client import BankingApiClient


def get_customer_profile(customer_id: str) -> dict:
    client = BankingApiClient()
    return client.get(f"/api/banking/customers/{customer_id}")
