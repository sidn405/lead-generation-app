import os, stripe, json
from flask import Flask, request, abort

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

app = Flask(__name__)

# you need to import your DB layer here
from postgres_credit_system import postgres_credit_system as credit_system

@app.post("/stripe/webhook")
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except Exception as e:
        print(f"[webhook] signature error: {e}")
        abort(400)

    t = event["type"]
    data = event["data"]["object"]

    # 1) Checkout completed (capture customer/subscription on first purchase)
    if t == "checkout.session.completed":
        try:
            sess = stripe.checkout.Session.retrieve(
                data["id"], expand=["subscription", "customer"]
            )
            username = (sess.get("metadata") or {}).get("username")  # set metadata at session creation if you can
            if username:
                sub  = sess.subscription
                cust = sess.customer
                credit_system.set_stripe_billing(
                    username=username,
                    customer_id=(cust.id if cust else None),
                    subscription_id=(sub.id if sub else None),
                    status=(sub.status if sub else None),
                    current_period_end=(sub.current_period_end if sub else None),
                )
        except Exception as e:
            print(f"[webhook] checkout.session.completed failed: {e}")

    # 2) Monthly charge success -> add monthly credits
    elif t == "invoice.payment_succeeded":
        try:
            sub_id = data.get("subscription")
            if not sub_id:
                return ("", 200)
            username = credit_system.find_user_by_subscription(sub_id)
            if not username:
                return ("", 200)

            # retrieve user's monthly_credits (saved at plan activation)
            info = credit_system.get_user_info(username) or {}
            monthly = int(info.get("monthly_credits", 0) or 0)
            if monthly > 0:
                credit_system.add_credits(
                    username,
                    monthly,
                    plan="subscription_monthly",
                    stripe_invoice_id=data.get("id"),
                )
            # keep status/dates fresh
            period = data.get("lines", {}).get("data", [{}])[0].get("period", {})
            credit_system.update_subscription_status(
                username,
                status="active",
                current_period_end=period.get("end"),
            )
        except Exception as e:
            print(f"[webhook] invoice.payment_succeeded failed: {e}")

    # 3) Payment failed / subscription updated / canceled
    elif t in ("invoice.payment_failed", "customer.subscription.updated", "customer.subscription.deleted"):
        try:
            if t == "invoice.payment_failed":
                sub_id = data.get("subscription")
                status = "past_due"
                period_end = None
            else:
                sub_id = data.get("id") if "subscription" in data else data.get("subscription")
                status = data.get("status", "canceled")
                period_end = data.get("current_period_end")

            if not sub_id:
                return ("", 200)

            username = credit_system.find_user_by_subscription(sub_id)
            if username:
                credit_system.update_subscription_status(
                    username,
                    status=status,
                    current_period_end=period_end,
                )
        except Exception as e:
            print(f"[webhook] {t} failed: {e}")

    return ("", 200)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
