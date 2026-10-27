"""Flask entry point. On Azure App Service: gunicorn --bind=0.0.0.0 --timeout 600 app:app"""
import os

from flask import Flask, jsonify, request

from orders import Customer, OrderRejected, place_order

app = Flask(__name__)
ORDERS: list = []
CUSTOMERS = {"C1": Customer("C1", "Active"), "C2": Customer("C2", "Inactive")}


@app.get("/health")
def health():
    if os.getenv("SIMULATE_FAILURE") == "true":            # Module 5 rollback exercise only
        return jsonify(status="failing", version=os.getenv("APP_VERSION", "local")), 503
    return jsonify(
        status="ok",
        version=os.getenv("APP_VERSION", "local"),          # set by the pipeline at deploy time
        env=os.getenv("APP_ENV", "local"),
        paymentKeyConfigured=payment_key_configured(),
    )


def payment_key_configured() -> bool:
    """True only when App Service resolved the Key Vault reference (Module 6).
    An unresolved reference arrives as the literal '@Microsoft.KeyVault(...)' text."""
    value = os.getenv("PAYMENT_GATEWAY_KEY", "")
    return bool(value) and not value.startswith("@Microsoft.KeyVault")


@app.post("/orders")
def create_order():
    body = request.get_json(force=True)
    customer = CUSTOMERS.get(body.get("customer_id"))
    if customer is None:
        return jsonify(error="unknown customer"), 404
    try:
        order = place_order(customer, float(body.get("amount", 0)), ORDERS)
    except OrderRejected as exc:
        return jsonify(error=str(exc)), 422
    return jsonify(order), 201
