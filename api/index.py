from fastapi import FastAPI

app = FastAPI(title="Fintech Microservices Core", version="1.0.0")


@app.get("/")
def root():
    return {
        "service": "fintech-microservices-core",
        "status": "ok",
        "routes": [
            "/api/v1/cards/issue",
            "/api/v1/funds/load",
            "/webhook/fiat_received",
            "/internal/transfer_funds"
        ]
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
