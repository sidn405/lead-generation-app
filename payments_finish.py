# payments_finish.py
import streamlit as st
from urllib.parse import unquote_plus

def handle_payment_success_url(simple_auth, credit_system):
    """Finalize the purchase using only URL params, then refresh UI."""
    qp = st.query_params
    if not qp.get("payment_success"):
        return False

    username = simple_auth.get_current_user()
    if not username:
        st.error("You're not signed in.")
        return True

    # pull details from success_url
    plan_raw = qp.get("plan", "").lower()
    credits = int(qp.get("credits", "0") or 0)
    session_id = qp.get("session_id", "")

    # normalize plan names used by your DB layer
    plan_map = {"starter": "starter", "pro": "pro", "ultimate": "ultimate",
                "lead starter":"starter","lead pro":"pro","lead empire":"ultimate"}
    plan = plan_map.get(plan_raw, "")

    # add credits / activate subscription (your DB helpers already exist)
    if plan in ("starter","pro","ultimate"):
        # monthly plan style:
        monthly = {"starter":250,"pro":2000,"ultimate":9999}[plan]
        credit_system.activate_subscription(username, plan, monthly, session_id)
    elif credits > 0:
        credit_system.add_credits(username, credits, plan or "credit_purchase", session_id)
    else:
        st.warning("Purchase detected but plan/credits missing in redirect URL.")

    # hard refresh session cache used by header badges, tabs, etc.
    fresh = credit_system.get_user_info(username)
    if fresh:
        st.session_state.user_data = {
            **st.session_state.get("user_data", {}),
            "plan": fresh.get("plan","demo"),
            "credits": fresh.get("credits",0)
        }

    # show a quick confirmation
    st.success("✅ Purchase complete! Updating your account…")

    # clear query params and rerun so tabs render content again
    st.query_params.clear()
    st.rerun()
    return True
