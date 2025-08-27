
# package_system.py — Postgres + custom/prebuilt flow (alignment-safe)
import os
import base64
from typing import Optional, Dict
from urllib.parse import quote_plus
import json
import streamlit as st
import stripe
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus, urlencode


# -----------------------------
# Environment & configuration
# -----------------------------

APP_BASE_URL = os.getenv("APP_BASE_URL", "https://leadgeneratorempire.com")

@st.cache_resource
def get_pg_engine():
    '''Return a cached SQLAlchemy engine for Postgres.'''
    url = os.getenv("DATABASE_URL") or os.getenv("RAILWAY_DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL/RAILWAY_DATABASE_URL is not set")
    # SQLAlchemy requires postgresql+psycopg2 scheme
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    engine = create_engine(url, pool_pre_ping=True)
    # Ensure tables exist
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS package_purchases (
                id BIGSERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                package_name TEXT NOT NULL,
                lead_count INTEGER NOT NULL,
                price NUMERIC(10,2) NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                download_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE (username, package_name)
            )
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS custom_orders (
                id BIGSERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                package_key TEXT NOT NULL,
                package_name TEXT NOT NULL,
                industry TEXT,
                location TEXT,
                price NUMERIC(10,2) NOT NULL,
                stripe_session_id TEXT,
                status TEXT NOT NULL DEFAULT 'new',  -- new,in_progress,ready,delivered,cancelled
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        '''))
    return engine

# -----------------------------
# Package definitions
# -----------------------------

PACKAGES: Dict[str, Dict[str, object]] = {
    # display name: leads/price/file
    "Niche Starter Pack": {"leads": 500, "price": 97, "file": "fitness_wellness_500.csv"},
    "Industry Deep Dive": {"leads": 2000, "price": 297, "file": "fitness_wellness_2000.csv"},
    "Market Domination":  {"leads": 5000, "price": 897, "file": "fitness_wellness_5000.csv"},
}

KEY_TO_NAME = {
    "starter": "Niche Starter Pack",
    "deep_dive": "Industry Deep Dive",
    "domination": "Market Domination",
}

# -----------------------------
# FS helpers
# -----------------------------

def ensure_leads_dir():
    os.makedirs("leads", exist_ok=True)

def _file_exists_in_leads(file_path: str) -> bool:
    return os.path.exists(os.path.join("leads", file_path))

# -----------------------------
# Database helpers (Postgres)
# -----------------------------


def remember_checkout_session(username: str, kind: str, session_id: str, payload: dict) -> None:
    engine = get_pg_engine()
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS pending_checkouts (
          id BIGSERIAL PRIMARY KEY,
          username TEXT NOT NULL,
          kind TEXT NOT NULL,             -- 'package' | 'subscription' | 'credits'
          session_id TEXT NOT NULL,
          payload JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          resolved_at TIMESTAMPTZ
        )"""))
        conn.execute(text("""
            INSERT INTO pending_checkouts (username, kind, session_id, payload)
            VALUES (:u, :k, :sid, :p)
        """), dict(u=username, k=kind, sid=session_id, p=json.dumps(payload)))

def get_latest_pending_checkout(username: str, kind: str = "package"):
    engine = get_pg_engine()
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT id, session_id, payload
            FROM pending_checkouts
            WHERE username = :u AND kind = :k AND resolved_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
        """), dict(u=username, k=kind)).mappings().first()
    return row

def resolve_pending_checkout(pending_id: int) -> None:
    engine = get_pg_engine()
    with engine.begin() as conn:
        conn.execute(text("UPDATE pending_checkouts SET resolved_at = NOW() WHERE id = :id"),
                     dict(id=pending_id))

def add_package_to_database(username: str, package_name: str) -> None:
    '''Add a pre-built package to the user's downloads (idempotent).'''
    pkg = PACKAGES.get(package_name)
    if not pkg:
        raise ValueError(f"Unknown package: {package_name}")
    engine = get_pg_engine()
    with engine.begin() as conn:
        conn.execute(
            text('''
                INSERT INTO package_purchases (username, package_name, lead_count, price, file_path)
                VALUES (:u, :n, :leads, :price, :file)
                ON CONFLICT (username, package_name) DO NOTHING
            '''),
            dict(u=username, n=package_name, leads=pkg["leads"], price=pkg["price"], file=pkg["file"]),
        )

def create_custom_order_record(
    username: str,
    package_key: str,
    package_name: str,
    industry: Optional[str],
    location: Optional[str],
    price: float,
    stripe_session_id: str = "",
) -> int:
    engine = get_pg_engine()
    with engine.begin() as conn:
        order_id = conn.execute(
            text('''
                INSERT INTO custom_orders (username, package_key, package_name, industry, location, price, stripe_session_id)
                VALUES (:u, :k, :n, :i, :l, :p, :sid)
                RETURNING id
            '''),
            dict(u=username, k=package_key, n=package_name, i=industry, l=location, p=price, sid=stripe_session_id),
        ).scalar_one()
    return order_id

def mark_custom_order_ready(order_id: int, username: str, package_name: str) -> None:
    '''Mark a custom order ready and add to downloads.'''
    add_package_to_database(username, package_name)
    engine = get_pg_engine()
    with engine.begin() as conn:
        conn.execute(text('''UPDATE custom_orders SET status='ready' WHERE id=:id AND username=:u'''),
                     dict(id=order_id, u=username))

def increment_download_count_by_name(username: str, package_name: str) -> None:
    engine = get_pg_engine()
    with engine.begin() as conn:
        conn.execute(text('''
            UPDATE package_purchases
            SET download_count = download_count + 1
            WHERE username = :u AND package_name = :n
        '''), dict(u=username, n=package_name))

# -----------------------------
# Stripe checkout
# -----------------------------

def create_package_stripe_session(
    api_key: str,
    username: str,
    package_key: str,
    price: float,
    package_name: str,
    industry: str = None,
    location: str = None,
    requires_build: bool = False,
):
    """Create a Stripe Checkout Session for a package purchase."""
    stripe.api_key = api_key

    display = package_name or {
        "starter": "Niche Starter Pack",
        "deep_dive": "Industry Deep Dive",
        "domination": "Market Domination",
    }.get(package_key, package_key)

    base = os.getenv("APP_BASE_URL", "https://leadgeneratorempire.com").rstrip("/")
    stamp = os.environ.get("APP_COMMIT", "")[:7] or "dev"
    ind = quote_plus(industry or "Fitness & Wellness")
    loc = quote_plus(location or "United States")

    session = stripe.checkout.Session.create(
        client_reference_id=username,
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": f"{'Custom ' if requires_build else ''}{display}",
                    "description": (
                        "Built-to-order • Allow 48–120 hours"
                        if requires_build else
                        "Verified leads • Instant download"
                    ),
                },
                "unit_amount": int(round(float(price) * 100)),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=(
            f"{base}/?success=1"
            f"&package_success=1"
            f"&package={quote_plus(package_key)}"
            f"&package_name={quote_plus(display)}"
            f"&username={quote_plus(username)}"
            f"&amount={price}"
            f"&industry={ind}"
            f"&location={loc}"
            f"&requires_build={'1' if requires_build else '0'}"
            f"&timestamp={stamp}"
            f"&session_id={{CHECKOUT_SESSION_ID}}"
        ),
        cancel_url=(
            f"{base}/?success=0"
            f"&cancel=1"
            f"&package={quote_plus(package_key)}"
            f"&username={quote_plus(username)}"
            f"&industry={ind}"
            f"&location={loc}"
        ),
        customer_email=f"{username}@example.com",
        metadata={
            "username": username,
            "package_name": display,
            "package_key": package_key,
            "industry": industry or "",
            "location": location or "",
            "requires_build": "1" if requires_build else "0",
            "order_type": "custom" if requires_build else "prebuilt",
        },
    )

    # remember the session in case user returns without query params
    st.session_state["last_checkout_session_id"] = session.id
    st.session_state["last_checkout_kind"] = "package"
    st.session_state["last_checkout_payload"] = {
        "package_key": package_key,
        "package_name": display,
        "requires_build": bool(requires_build),
        "industry": industry or "",
        "location": location or "",
        "amount": float(price),
    }

    st.success("✅ Checkout session created! Redirecting to Stripe…")
    st.markdown(
        f"""
        <meta http-equiv="refresh" content="2;url={session.url}">
        <div style="text-align:center;padding:20px;">
            <h3>🔄 Redirecting to Stripe…</h3>
            <p>If you're not redirected automatically:</p>
            <a href="{session.url}" target="_blank" style="
                background:#635bff;color:white;padding:12px 20px;
                border-radius:8px;text-decoration:none;font-weight:600;">
                🚀 Open Checkout
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return session


# -----------------------------
# UI helpers (Store & Downloads)
# -----------------------------

def show_package_store(username: str, user_authenticated: bool):
    # cancelled?
    if (
        st.query_params.get("success") == "0"
        or "cancel" in st.query_params
        or "package_cancelled" in st.query_params
    ):
        st.warning("⚠️ Purchase was cancelled. You can try again anytime.")
        st.query_params.clear()
        st.rerun()

    st.markdown('<div id="top"></div>', unsafe_allow_html=True)
    st.markdown("# 📦 Pre-Built Lead Packages")

    # Targeting summary banner
    st.markdown("## 📋 Your Targeting Summary")
    st.markdown("""
    <div style="background-color:#1e3a5f; padding:20px; border-radius:10px; margin-bottom:20px;">
      <div style="color:#60a5fa; margin-bottom:8px;">🏢 <strong>Industry:</strong> Fitness & Wellness</div>
      <div style="color:#60a5fa; margin-bottom:8px;">📍 <strong>Location:</strong> United States (All States)</div>
      <div style="color:#60a5fa;">👥 <strong>Lead Type:</strong> End Customers</div>
    </div>
    """, unsafe_allow_html=True)
    st.success("🚀 **FITNESS & WELLNESS LEADS PRE-BUILT & READY** — Instant download available")
    st.markdown("---")

    packages = [
        {"key":"starter","name":"Niche Starter Pack","badge":"STARTER","badge_color":"#1f77b4","leads":500,"price":97,
         "features":["500 targeted leads in your chosen industry","2-3 platforms included","Basic filtering applied",
                     "CSV + Google Sheets delivery","48-hour delivery"],
         "perfect_for":"Testing a new niche, quick campaigns"},
        {"key":"deep_dive","name":"Industry Deep Dive","badge":"MOST POPULAR","badge_color":"#28a745","leads":2000,"price":297,
         "features":["2,000 highly-targeted leads in your industry","Comprehensive industry research","All 8 platforms",
                     "Advanced relevance filtering","Social media profiles included","DMs pre-generated for your industry","72-hour delivery"],
         "perfect_for":"Serious campaigns, market research"},
        {"key":"domination","name":"Market Domination","badge":"ENTERPRISE","badge_color":"#fd7e14","leads":5000,"price":897,
         "features":["5,000 premium leads across multiple related niches","Advanced geographic targeting",
                     "Phone/email enrichment when available","Custom DM sequences for your industry",
                     "30-day refresh guarantee","5 business days delivery"],
         "perfect_for":"Enterprise campaigns, market domination"},
    ]

    cols = st.columns(3)
    for pkg, col in zip(packages, cols):
        with col:
            st.markdown(f"""
                <div style="background-color:{pkg['badge_color']};color:white;padding:8px 16px;
                            border-radius:8px;text-align:center;font-weight:bold;margin-bottom:16px;">
                    {pkg['badge']}
                </div>
            """, unsafe_allow_html=True)
            st.markdown(f"### {pkg['name']}")
            st.markdown(f"## ${pkg['price']}")
            st.markdown(f"**{pkg['leads']:,} verified leads**")
            st.markdown("---")
            st.markdown("**📦 What's Included:**")
            for feat in pkg["features"]:
                st.markdown(f"• {feat}")
            st.info(f"**Perfect for:** {pkg['perfect_for']}")

            agree_key = f"agree_{pkg['key']}"
            if agree_key not in st.session_state:
                st.session_state[agree_key] = False
            agreed = st.checkbox("✅ Agree to terms", key=agree_key,
                                 help="I agree to the Terms of Service & No-Refund Policy",
                                 value=st.session_state.get(agree_key, False))

            if user_authenticated:
                button_text = f"🛒 Buy {pkg['name']}" if agreed else f"🛒 Buy {pkg['name']} (Agree to terms first)"
                if st.button(button_text, key=f"buy_{pkg['key']}", disabled=not agreed, use_container_width=True,
                             type=("primary" if agreed else "secondary")):
                    if agreed:
                        create_package_stripe_session(
                            os.getenv("STRIPE_SECRET_KEY", ""),
                            username,
                            pkg["key"],
                            pkg["price"],
                            pkg["name"],
                            industry="Fitness & Wellness",
                            location="United States",
                            requires_build=False,  # pre-built store
                        )
            else:
                if st.button("🔑 Sign In to Buy", key=f"signin_{pkg['key']}", use_container_width=True):
                    st.session_state.show_login = True
                    st.rerun()

    # Sticky "Top" and footer
    st.markdown(
        '<a href="#top" style="position:fixed;bottom:20px;right:20px;'
        'padding:12px 16px;border-radius:25px;background:linear-gradient(135deg,#0066cc,#4dabf7);'
        'color:white;font-weight:bold;text-decoration:none;z-index:9999;">⬆️ Top</a>',
        unsafe_allow_html=True,
    )
    st.markdown("""
      <style>
        .appview-container .main { padding-bottom: 60px; }
        .footer { position:fixed; bottom:0; left:0; width:100%; height:50px;
                  background:rgba(0,0,0,0.8); color:#aaa; display:flex; align-items:center;
                  justify-content:center; font-size:0.9rem; z-index:1000; }
      </style>
      <div class="footer">Lead Generator Empire Pre-Built Packages | Secure &amp; Private</div>
    """, unsafe_allow_html=True)


def _render_data_uri_download(username: str, package_name: str, file_path: str):
    ensure_leads_dir()
    full_path = os.path.join("leads", file_path)
    try:
        with open(full_path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        st.error(f"File missing on server: {full_path}. Contact support.")
        return
    b64 = base64.b64encode(data).decode()
    filename = f"{package_name.replace(' ', '_').lower()}_fitness_wellness_leads.csv"
    st.markdown('''
        <div style="background:#102a43;padding:16px;border-radius:10px;margin:16px 0;text-align:center;">
          <a href="data:file/csv;base64,{b64}" download="{filename}" 
             style="background:#28a745;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block;margin-bottom:8px;">
             Download {filename}
          </a>
          <div style="color:#cbd5e1;font-size:14px;">Tip: Import into your CRM or outreach tool.</div>
        </div>
    '''.format(b64=b64, filename=filename), unsafe_allow_html=True)
    increment_download_count_by_name(username, package_name)

def show_my_packages(username: str):
    st.title("📁 My Downloaded Packages")

    # Handle Stripe success via query params (legacy path still works)
    if "package_success" in st.query_params:
        raw = st.query_params.get("package", "unknown")
        name_map = {"starter":"Niche Starter Pack","deep_dive":"Industry Deep Dive","domination":"Market Domination"}
        add_package_to_database(username, name_map.get(raw, raw))
        st.success(f"🎉 {name_map.get(raw, raw)} purchased successfully!")
        st.info("📁 Your package is now available for download below")
        st.query_params.clear()
        st.rerun()

    # Load purchases (Postgres if available; else SQLite fallback)
    rows = []
    try:
        # If you're on Postgres with SQLAlchemy
        from sqlalchemy import text as _text
        engine = get_pg_engine()  # comment out if not using the Postgres helpers
        with engine.begin() as conn:
            rows = conn.execute(_text("""
                SELECT package_name, lead_count, price, file_path, created_at, download_count
                FROM package_purchases
                WHERE username = :u
                ORDER BY created_at DESC
            """), dict(u=username)).fetchall()
    except Exception:
        # SQLite fallback (backup behavior)
        import sqlite3
        conn = sqlite3.connect("lead_generator.db")
        cur = conn.cursor()
        cur.execute("""
            SELECT package_name, lead_count, price, file_path, purchase_date, download_count
            FROM package_purchases
            WHERE username = ?
            ORDER BY purchase_date DESC
        """, (username,))
        rows = cur.fetchall()
        conn.close()

    if not rows:
        st.info("📦 No packages purchased yet.")
        st.markdown("Visit the **Package Store** to get instant-download lead packages!")
        if st.button("🛒 Browse Packages", type="primary"):
            st.session_state.current_page = "Package Store"
            st.rerun()
        return

    st.success(f"You have {len(rows)} package(s) available for download")
    for (name, leads, price, file_path, created_at, dl_count) in rows:
        st.markdown(f"### 📦 {name}")
        st.markdown(
            f"**📊 Lead Count:** {leads:,}  \n"
            f"**💰 Price Paid:** ${price}  \n"
            f"**📅 Purchase Date:** {created_at}  \n"
            f"**📥 Downloads:** {dl_count}"
        )

        full_path = os.path.join("leads", file_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                filename = f"{name.replace(' ', '_').lower()}_fitness_wellness_leads.csv"
                st.markdown(f"""
                <div style="background-color:#1e3a5f;padding:20px;border-radius:10px;margin:20px 0;text-align:center;">
                  <a href="data:file/csv;base64,{b64}" download="{filename}"
                     style="background-color:#28a745;color:white;padding:15px 30px;
                            text-decoration:none;border-radius:8px;font-weight:bold;font-size:16px;
                            display:inline-block;margin-bottom:15px;">
                    📥 Download {filename}
                  </a>
                  <div style="color:#60a5fa;font-size:14px;margin-top:15px;padding:10px;
                              background-color:rgba(96,165,250,0.1);border-radius:6px;">
                    💡 <strong>Tip:</strong> Import this CSV into your CRM or outreach tool.
                  </div>
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error preparing download: {e}")
        else:
            st.error("❌ File missing")

        st.markdown("---")

        
        

