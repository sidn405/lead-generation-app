
# package_system.py — Postgres + custom/prebuilt flow (alignment-safe)
import os
import base64
from typing import Optional, Dict
from urllib.parse import quote_plus

import streamlit as st
import stripe
from sqlalchemy import create_engine, text

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
    industry: Optional[str] = None,
    location: Optional[str] = None,
    requires_build: bool = False,
):
    '''Create a Stripe Checkout Session for a package purchase.
    Set requires_build=True for custom/build-to-order packages.
    '''
    stripe.api_key = api_key

    # Human name and QS-safe strings
    display = package_name or KEY_TO_NAME.get(package_key, package_key)
    ind = quote_plus(industry or "Fitness & Wellness")
    loc = quote_plus(location or "United States")

    # canonical base (supports reverse proxy)
    base = APP_BASE_URL.rstrip("/")
    stamp = os.environ.get("APP_COMMIT", "")[:7] or "dev"

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": f"{('Custom ' if requires_build else '')}{display}",
                    "description": (
                        "Built-to-order • Allow 48–120 hours"
                        if requires_build else
                        "Verified leads • Instant download"
                    ),
                },
                "unit_amount": int(float(price) * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=(
            f"{base}/?success=1"
            f"&package_success=1"
            f"&package={quote_plus(display)}"
            f"&package_key={quote_plus(package_key)}"
            f"&username={quote_plus(username)}"
            f"&amount={price}"
            f"&industry={ind}"
            f"&location={loc}"
            f"&requires_build={(1 if requires_build else 0)}"
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

    # Friendly redirect hint
    st.success("✅ Checkout session created! Redirecting to Stripe…")
    st.markdown('''
        <meta http-equiv="refresh" content="2;url={url}">
        <div style="text-align:center;padding:20px;">
          <h3>Redirecting to Stripe</h3>
          <p>If you're not redirected automatically:</p>
          <a href="{url}" target="_blank" style="background:#635bff;color:white;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600;">Open Checkout</a>
        </div>
    '''.replace("{url}", session.url), unsafe_allow_html=True)

    return session

# -----------------------------
# UI helpers (Store & Downloads)
# -----------------------------

def show_package_store(username: str, industry: Optional[str] = None, location: Optional[str] = None,
                       api_key: Optional[str] = None):
    '''Minimal store that sells the 3 pre-built packages (instant download).'''
    api_key = api_key or os.getenv("STRIPE_SECRET_KEY", "")
    st.subheader("Package Store")
    cols = st.columns(3)
    entries = [
        ("starter", "Niche Starter Pack", 97),
        ("deep_dive", "Industry Deep Dive", 297),
        ("domination", "Market Domination", 897),
    ]
    for col, (key, name, price) in zip(cols, entries):
        with col:
            st.markdown(f"### {name}")
            st.markdown(f"**${price}**")
            if st.button(f"Buy {name}", key=f"buy_{key}"):
                create_package_stripe_session(
                    api_key=api_key,
                    username=username,
                    package_key=key,
                    price=price,
                    package_name=name,
                    industry=industry,
                    location=location,
                    requires_build=False,  # pre-built
                )

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
    '''List purchased packages (from Postgres) and provide download links.'''
    st.subheader("My Downloads")
    engine = get_pg_engine()
    with engine.begin() as conn:
        rows = conn.execute(text('''
            SELECT package_name, lead_count, price, file_path, created_at, download_count
            FROM package_purchases
            WHERE username = :u
            ORDER BY created_at DESC
        '''), dict(u=username)).fetchall()
    if not rows:
        st.info("No packages yet.")
        return
    for row in rows:
        name, leads, price, file_path, created_at, dl_count = row
        st.markdown(f"### 📦 {name}")
        try:
            purchased = created_at.strftime("%Y-%m-%d %H:%M")
        except Exception:
            purchased = str(created_at)
        st.caption(f"Leads: {leads:,} • Price: ${price} • Purchased: {purchased} • Downloads: {dl_count}")
        if _file_exists_in_leads(file_path):
            _render_data_uri_download(username, name, file_path)
        else:
            st.error(f"File missing on server: leads/{file_path}. Contact support.")
        st.markdown("---")
