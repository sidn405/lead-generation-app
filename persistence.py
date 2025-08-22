# persistence.py
from pathlib import Path
import os
import csv

def _resolve_csv_dir(csv_dir=None):
    """Prefer caller-provided path; else env; else /client_configs."""
    if csv_dir:
        return Path(csv_dir)
    env_dir = os.getenv("CSV_DIR")
    return Path(env_dir) if env_dir else Path("/client_configs")

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
    """
    Save processed and (optionally) raw leads to CSVs.
    Returns list[str] of saved file paths.

    - If csv_dir is None, uses env CSV_DIR or /client_configs.
    - platform_name is used to prefix files: e.g. twitter_leads_<user>_<ts>.csv
    - If record_to_credit_system=True and a global credit_system exists
      with record_lead_download(username, platform, leads_count), it will be called.
    """
    files_saved = []
    out_dir = _resolve_csv_dir(csv_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    platform_key = (platform_name or "platform").strip().lower().replace(" ", "") or "platform"

    fieldnames = [
        'name','handle','bio','url','platform','dm','title','location',
        'followers','profile_url','contact_info','search_term',
        'extraction_method','relevance_score'
    ]

    # 1) processed
    if leads:
        out_name = f"{platform_key}_leads_{username}_{timestamp}.csv"
        out_path = out_dir / out_name
        with out_path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(leads)
        files_saved.append(str(out_path))
        print(f"✅ Saved processed leads → {out_path}")

        # Optional: record a lead_download so your dashboard shows immediately
        if record_to_credit_system:
            try:
                credit_system = globals().get("credit_system", None)
                if credit_system and hasattr(credit_system, "record_lead_download"):
                    credit_system.record_lead_download(
                        username=username,
                        platform=platform_key,
                        leads_count=len(leads),
                    )
            except Exception as e:
                print(f"ℹ️ Could not record lead_download: {e}")

    # 2) raw (only if different length or no processed)
    if raw_leads and save_raw and (not leads or len(raw_leads) != len(leads)):
        raw_name = f"{platform_key}_leads_raw_{username}_{timestamp}.csv"
        raw_path = out_dir / raw_name
        with raw_path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(raw_leads)
        files_saved.append(str(raw_path))
        print(f"📋 Saved raw leads → {raw_path}")

    return files_saved
