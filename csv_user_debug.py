# csv_user_debug.py  — robust, username-aware CSV lookups under CSV_DIR

from __future__ import annotations
import os, re, glob
from pathlib import Path
from typing import Optional
import pandas as pd

# Always search inside your app's CSV directory (can be overridden via env)
CSV_DIR = Path(os.environ.get("CSV_DIR", "client_configs")).resolve()

class CSVUserDebugger:
    # Columns that may indicate ownership
    USER_COLS = ("generated_by", "username", "user_id", "created_by", "owner")

    def _file_belongs_to_user(self, filepath: str, username: str) -> bool:
        """
        Return True if this CSV clearly belongs to `username`, using filename or
        explicit user columns. (No 'recent file' heuristics.)
        """
        if not username:
            return False

        base = os.path.basename(filepath)
        uname = re.escape(username)

        # 1) Filename contains username as a token (case-insensitive)
        #    e.g., twitter_leads_jane_2025-08-26.csv
        if re.search(rf"(^|[_\-]){uname}([_\-]|\.|\d)", base, re.IGNORECASE):
            return True

        # 2) CSV content has an explicit user column matching username
        try:
            # Read a reasonable number of rows for speed
            df = pd.read_csv(filepath, nrows=5000)
        except Exception:
            return False

        u_lc = username.lower()
        for col in self.USER_COLS:
            if col in df.columns:
                s = df[col].astype(str).str.lower()
                if (s == u_lc).any():
                    return True

        return False


def filter_csv_for_user(df: pd.DataFrame, username: str) -> pd.DataFrame:
    """
    Filter a DataFrame to rows owned by `username`, if recognizable user columns exist.
    Otherwise, return df unchanged.
    """
    if not isinstance(df, pd.DataFrame) or not username:
        return df

    u_lc = username.lower()
    for col in CSVUserDebugger.USER_COLS:
        if col in df.columns:
            return df[df[col].astype(str).str.lower() == u_lc]

    return df


def get_user_csv_file(pattern: str, username: str) -> Optional[str]:
    """
    Return the newest CSV under CSV_DIR matching `pattern` that belongs to `username`.

    - If `pattern` already contains the username, we DO NOT inject it again.
    - We search CSV_DIR and CSV_DIR/** recursively.
    - We do NOT use 'recency' as a proxy for ownership (multi-user safe).
    """
    dbg = CSVUserDebugger()

    if not username:
        print("❌ No username provided")
        return None

    def _glob_under(pat: str):
        base_glob = str(CSV_DIR / pat)
        rec_glob  = str(CSV_DIR / "**" / pat)
        files = glob.glob(base_glob) + glob.glob(rec_glob, recursive=True)
        files.sort(key=os.path.getmtime, reverse=True)
        return files

    # If the incoming pattern already includes the username, use it as-is.
    if re.search(re.escape(username), pattern, re.IGNORECASE):
        files = _glob_under(pattern)
        if files:
            print(f"✅ Using already-userized pattern: {pattern} -> {files[0]}")
            return files[0]
        print(f"❌ No files for already-userized pattern: {pattern}")
        return None

    # Otherwise, try a few safe injections (NO duplication).
    candidates = []

    # Common shapes in your app:
    #   "<prefix>_*_*.csv"  ->  "<prefix>_*<username>_*.csv"
    #   "<prefix>_*.csv"    ->  "<prefix>_<username>_*.csv"
    if "*_*.csv" in pattern:
        candidates.append(pattern.replace("*_*.csv", f"*{username}_*.csv"))
    if "_*.csv" in pattern:
        candidates.append(pattern.replace("_*.csv", f"_{username}_*.csv"))
    if "*.csv" in pattern and f"{username}*.csv" not in pattern:
        candidates.append(pattern.replace("*.csv", f"{username}*.csv"))

    # De-dup while preserving order
    for pat in dict.fromkeys(candidates):
        files = _glob_under(pat)
        if files:
            print(f"✅ Found user-specific file with pattern {pat}: {files[0]}")
            return files[0]
        else:
            print(f"❌ No files found for pattern: {pat}")

    # Last resort: check base pattern and verify by content/filename ownership
    print(f"🔍 Checking base pattern via content ownership: {pattern}")
    for fp in _glob_under(pattern):
        if dbg._file_belongs_to_user(fp, username):
            print(f"✅ Found user file via content analysis: {fp}")
            return fp

    return None
