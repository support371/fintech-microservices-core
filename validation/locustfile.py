from locust import HttpUser, task, between
import uuid

class ConverterServiceUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def transfer_funds(self):
        headers = {"Content-Type": "application/json"}
        payload = {
            "user_id": f"user_{uuid.uuid4()}",
            "fiat_amount": 100.0,
            "fiat_currency": "USD",
            "trace_id": str(uuid.uuid4())
        }
        self.client.post("/internal/transfer_funds", json=payload, headers=headers)
