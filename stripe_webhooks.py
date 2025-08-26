# stripe_webhook.py
import os, json, stripe
from flask import Flask, request, Response
from postgres_credit_system import credit_system

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

PLAN_CREDITS = {"starter": 250, "pro": 2000, "ultimate": 5000}

app = Flask(__name__)

def _activate_user_plan(username: str, plan: str, customer_id: str, subscription_id: str):
    info = credit_system.get_user_info(username) or {}
    # set plan + subscription markers
    info.update({
        "plan": plan,
        "subscribed_plan": plan,
        "subscription_status": "active",
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
    })
    # grant monthly credits on first activation
    monthly = PLAN_CREDITS.get(plan, 0)
    info["credits"] = int(info.get("credits", 0)) + monthly
    credit_system.save_user_info(username, info)

@app.post("/stripe/webhook")
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except Exception as e:
        return Response(f"Invalid signature: {e}", 400)

    etype = event["type"]
    data = event["data"]["object"]

    # 1) New signup / first payment
    if etype == "checkout.session.completed":
        md = data.get("metadata") or {}
        username = md.get("username")
        plan = (md.get("plan") or "").lower()
        if username and plan:
            _activate_user_plan(
                username=username,
                plan=plan,
                customer_id=data.get("customer"),
                subscription_id=data.get("subscription"),
            )

    # 2) Subscription status changes (renewal, cancel, pause)
    elif etype in ("customer.subscription.updated", "customer.subscription.created"):
        sub = data
        status = sub.get("status")  # active, past_due, canceled, unpaid
        plan = (sub.get("items", {}).get("data", [{}])[0]
                    .get("price", {}).get("nickname", "")).lower()  # or map from price.id
        customer_id = sub.get("customer")
        # If you stored username on customer metadata, prefer that; otherwise map by customer id.
        username = (sub.get("metadata") or {}).get("username") or credit_system.lookup_username_by_customer(customer_id)
        if username:
            info = credit_system.get_user_info(username) or {}
            info.update({
                "subscription_status": status,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": sub.get("id"),
            })
            if plan:
                info["plan"] = info["subscribed_plan"] = plan
            credit_system.save_user_info(username, info)

    elif etype in ("customer.subscription.deleted", "invoice.payment_failed"):
        sub = data
        customer_id = sub.get("customer") if etype.startswith("customer.subscription") else sub.get("customer")
        username = credit_system.lookup_username_by_customer(customer_id)
        if username:
            info = credit_system.get_user_info(username) or {}
            info["subscription_status"] = "canceled"
            # Optional: downgrade plan on cancel
            info["plan"] = "starter" if info.get("starter_grace") else "demo"
            credit_system.save_user_info(username, info)

    return Response("OK", 200)
