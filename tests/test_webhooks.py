"""The Stripe webhook accepts an event only when its signature proves Stripe sent it."""

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from store.api.app import app
from store.config import settings

SECRET = "whsec_test_secret"
EVENT = json.dumps(
    {
        "id": "evt_test_1",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_1", "metadata": {"public_id": "MM-1042"}}},
    }
).encode()


def _sign(payload: bytes, *, secret: str = SECRET, age_seconds: int = 0) -> str:
    """Stripe's scheme, built by hand: HMAC-SHA256 of "<timestamp>.<payload>" with the endpoint's secret."""
    timestamp = int(time.time()) - age_seconds
    signature = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", SecretStr(SECRET))
    with TestClient(app) as c:
        yield c


def _post(client: TestClient, payload: bytes, signature: str | None):
    headers = {"Stripe-Signature": signature} if signature is not None else {}
    return client.post("/webhooks/stripe", content=payload, headers=headers)


def test_signed_event_is_acknowledged(client):
    r = _post(client, EVENT, _sign(EVENT))
    assert (r.status_code, r.json()) == (200, {"received": True})


@pytest.mark.parametrize(
    "signature",
    [
        pytest.param(None, id="no signature"),
        pytest.param("not-a-signature", id="malformed header"),
        pytest.param(_sign(EVENT, secret="whsec_someone_else"), id="signed with another secret"),
        pytest.param(_sign(EVENT.replace(b"MM-1042", b"MM-9999")), id="signature of a different body"),
        pytest.param(_sign(EVENT, age_seconds=600), id="replayed after 10 minutes"),
    ],
)
def test_anything_else_is_rejected(client, signature):
    r = _post(client, EVENT, signature)
    # A fixed message: Stripe's own error text can describe the configured secret.
    assert (r.status_code, r.json()) == (400, {"detail": "Invalid Stripe signature."})


def test_correctly_signed_garbage_is_rejected(client):
    r = _post(client, b"not json", _sign(b"not json"))
    assert (r.status_code, r.json()) == (400, {"detail": "Invalid payload."})


def test_without_a_configured_secret_nothing_is_accepted():
    with TestClient(app) as client:  # settings.stripe_webhook_secret is None here
        r = _post(client, EVENT, _sign(EVENT))
    assert r.status_code == 503
