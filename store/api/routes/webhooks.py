"""Webhooks from payment providers. Stripe signs every event, and nothing unsigned gets in."""

from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status

from store.config import settings

log = logging.getLogger("store.webhooks")
router = APIRouter(prefix="/webhooks")


@router.post("/stripe")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None)) -> dict[str, bool]:
    """Check that the event really comes from Stripe, then acknowledge it.

    Stub: acting on `checkout.session.completed` (mark the order paid, decrement stock,
    skip events already seen in stripe_events) arrives with the orders tables.
    """
    secret = settings.stripe_webhook_secret
    if secret is None:
        # Fail closed: without the signing secret nothing can be verified, so nothing is accepted.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Stripe webhooks are not configured.")

    payload = await request.body()  # the raw bytes: the signature covers exactly these
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, secret.get_secret_value())
    except stripe.SignatureVerificationError as exc:
        # Stripe's message can describe the configured secret, so the caller gets a fixed one.
        log.warning("rejected a Stripe webhook: signature check failed")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Stripe signature.") from exc
    except ValueError as exc:  # correctly signed, but not a Stripe event
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid payload.") from exc

    log.info("verified Stripe event %s (%s); no handler yet", event.id, event.type)
    return {"received": True}
