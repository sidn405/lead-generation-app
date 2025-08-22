
import hashlib, json, re
from pathlib import Path
from shutil import copy2

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
DIST = ASSETS / "dist"
DIST.mkdir(exist_ok=True)

# Files to hash + rewrite references for
FILES = [
    "favicon-16x16.png",
    "favicon-32x32.png",
    "favicon-180x180.png",
    "favicon-192x192.png",
    "favicon-256x256.png",
    "favicon-512x512.png",
    "apple-touch-icon.png",
    "logo-96.png",
    "logo-192.png",
    "logo-288.png",
    "manifest-fullscreen.json",
]

def short_hash(p: Path, n=6) -> str:
    h = hashlib.sha1(p.read_bytes()).hexdigest()
    return h[:n]

versions = {}
for name in FILES:
    src = ASSETS / name
    if not src.exists():
        continue
    if src.suffix.lower() == ".json":
        # copy JSON for now; rewrite after we know icon hashes
        copy2(src, DIST / name)
        continue
    h = short_hash(src)
    hashed = f"{src.stem}.{h}{src.suffix}"
    copy2(src, DIST / hashed)
    versions[name] = f"assets/dist/{hashed}"

# Update manifest to point to hashed icons (if present)
mf = DIST / "manifest-fullscreen.json"
if mf.exists():
    data = json.loads(mf.read_text())
    if "icons" in data:
        for icon in data["icons"]:
            src = icon.get("src", "")
            base = Path(src).name
            if base in versions:
                icon["src"] = versions[base]
    mf.write_text(json.dumps(data, indent=2))

# Write versions map + cache version
CACHE_VERSION = hashlib.sha1("".join(sorted(versions.values())).encode()).hexdigest()[:8]
out = {
    "map": versions,
    "cache_version": CACHE_VERSION
}
(ASSETS / "versions.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))