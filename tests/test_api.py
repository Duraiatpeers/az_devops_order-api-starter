from app import app


def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_health():
    r = client().get("/health")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


def test_create_order_for_active_customer():
    r = client().post("/orders", json={"customer_id": "C1", "amount": 1500})
    assert r.status_code == 201 and r.get_json()["total"] == 1350.0


def test_unknown_customer_gets_404():
    r = client().post("/orders", json={"customer_id": "X", "amount": 50})
    assert r.status_code == 404


def test_unresolved_key_vault_reference_is_not_configured(monkeypatch):
    monkeypatch.setenv("PAYMENT_GATEWAY_KEY", "@Microsoft.KeyVault(VaultName=kv;SecretName=PaymentGatewayKey)")
    assert client().get("/health").get_json()["paymentKeyConfigured"] is False


def test_resolved_key_is_configured(monkeypatch):
    monkeypatch.setenv("PAYMENT_GATEWAY_KEY", "test-value")
    assert client().get("/health").get_json()["paymentKeyConfigured"] is True


def test_simulated_failure_returns_503(monkeypatch):
    monkeypatch.setenv("SIMULATE_FAILURE", "true")
    assert client().get("/health").status_code == 503
