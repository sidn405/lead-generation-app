# persistence.py
from pathlib import Path
import os, csv, re  # add re

def _resolve_csv_dir(csv_dir=None):
    """Prefer caller-provided path; else env; else ./client_configs (NOT /client_configs)."""
    if isinstance(csv_dir, Path):
        return csv_dir
    if csv_dir:
        return Path(csv_dir)
    env_dir = os.getenv("CSV_DIR")
    return Path(env_dir) if env_dir else Path("client_configs")  # was Path("/client_configs")

def save_leads_to_files(
    leads,
    raw_leads,
    username: str,
    timestamp: str,
    platform_name: str,
    csv_dir=None,
    save_raw: bool = False,
    record_to_credit_system: bool = True,
):
    files_saved = []
    out_dir = _resolve_csv_dir(csv_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # normalize names so filenames are safe & consistent
    platform_key  = (platform_name or "platform").strip().lower().replace(" ", "") or "platform"
    safe_username = re.sub(r"[^A-Za-z0-9_-]+", "_", username or "anon")

    fieldnames = [
        'name','handle','bio','url','platform','dm','title','location',
        'followers','profile_url','contact_info','search_term',
        'extraction_method','relevance_score','is_verified','has_email','has_phone', 'subscriber_count', 'description', 'video_count', 'subscribers', 'channel_url', 'username', 'raw_text_sample', 'extracted_at',
        'transformation_stage', 'content_preview', 'post_title', 'pain_points', 'post_type', 'source_type', 'support_seeking', 'product_interest', 'source_post_url', 'search_source', 'lead_quality', 'customer_type', 'niche_goals',
        'urgency_level', 'article_context', 'comment_preview', 'source_article_url', 'content_engagement', 'content_focus', 'reading_patterns'
    ]

    # 1) processed
    if leads:
        out_name = f"{platform_key}_leads_{safe_username}_{timestamp}.csv"
        out_path = out_dir / out_name                               # keep all writes under out_dir
        with out_path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(leads)
        files_saved.append(str(out_path))
        print(f"✅ Saved processed leads → {out_path}")

        if record_to_credit_system:
            try:
                credit_system = globals().get("credit_system", None)
                if credit_system and hasattr(credit_system, "record_lead_download"):
                    credit_system.record_lead_download(
                        username=username, platform=platform_key, leads_count=len(leads)
                    )
            except Exception as e:
                print(f"ℹ️ Could not record lead_download: {e}")

    # 2) raw (only if different length or no processed)
    if raw_leads and save_raw and (not leads or len(raw_leads) != len(leads)):
        raw_name = f"{platform_key}_leads_raw_{safe_username}_{timestamp}.csv"
        raw_path = out_dir / raw_name                               # was Path(csv_dir) / raw_name
        with raw_path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(raw_leads)
        files_saved.append(str(raw_path))
        print(f"📋 Saved raw leads → {raw_path}")

    return files_saved
