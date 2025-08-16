# json_utils.py
import json, os, time

def _atomic_write_json(path: str, data: dict) -> None:
    tmp = f"{path}.tmp.{int(time.time()*1000)}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)

def load_json_safe(path: str, default=None):
    """
    Backward compatible: 'default' is optional.
    If default is omitted, use {} (a dict).
    Also repairs empty/corrupt/BOM files.
    """
    if default is None:
        default = {}  # keeps old one-arg callsites working

    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Missing or empty file -> create with default
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        _atomic_write_json(path, default)
        return default

    try:
        # utf-8-sig tolerates BOM
        with open(path, "r", encoding="utf-8-sig") as f:
            txt = f.read().strip()
        if not txt:
            _atomic_write_json(path, default)
            return default
        return json.loads(txt)

    except Exception:
        # salvage bad file, write default
        bad = f"{path}.bad.{int(time.time())}"
        try: os.replace(path, bad)
        except Exception: pass
        _atomic_write_json(path, default)
        return default
