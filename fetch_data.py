#!/usr/bin/env python3
"""
Live supply-chain concentration analysis for npm packages.

For each package we treat its set of direct runtime dependencies as a
"portfolio". Each dependency is weighted by its own install footprint
(the unpacked size in bytes of its latest release). From those weights we
compute the same concentration statistics an equity analyst would run on a
fund's holdings:

    * Largest %  - the single heaviest dependency's share of the footprint
    * Top 3 %    - combined share of the three heaviest dependencies
    * HHI        - Herfindahl-Hirschman Index, sum of squared shares (0-1)

The HHI is bucketed into a Low / Medium / High risk tag using the U.S.
DOJ / FTC merger-guideline thresholds (0.15 and 0.25 on the 0-1 scale),
which is a real, citable way to say "how concentrated is this?".

Data source: the public npm registry (https://registry.npmjs.org). No
API key, no third-party libraries — standard library only.
"""

import concurrent.futures as cf
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

REGISTRY = "https://registry.npmjs.org"
USER_AGENT = "npm-concentration-explorer (+https://registry.npmjs.org)"
HERE = os.path.dirname(os.path.abspath(__file__))

# HHI risk buckets on the normalized 0-1 scale (DOJ/FTC 1500 / 2500 points).
HHI_MODERATE = 0.15
HHI_HIGH = 0.25

# --- tiny thread-safe cache so shared dependencies are fetched only once ----
_cache = {}
_cache_lock = threading.Lock()


def fetch_json(url, retries=3):
    """GET a URL and parse JSON, with a couple of polite retries."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if attempt == retries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == retries - 1:
                raise
        time.sleep(1.5 * (attempt + 1))
    return None


def latest_manifest(pkg):
    """Latest-version manifest for a package (small doc, cached)."""
    with _cache_lock:
        if pkg in _cache:
            return _cache[pkg]
    url = f"{REGISTRY}/{urllib.parse.quote(pkg, safe='@/')}/latest"
    try:
        data = fetch_json(url)
    except Exception:
        data = None
    with _cache_lock:
        _cache[pkg] = data
    return data


def dependency_size(name):
    """Install footprint (unpacked bytes) of a dependency's latest release."""
    manifest = latest_manifest(name)
    if not manifest:
        return None
    return manifest.get("dist", {}).get("unpackedSize")


def risk_tag(hhi):
    if hhi >= HHI_HIGH:
        return "High"
    if hhi >= HHI_MODERATE:
        return "Medium"
    return "Low"


def build_record(pkg, manifest, size_of):
    """Turn a fetched manifest + a name->size lookup into one record, or None."""
    if not manifest:
        return None

    deps = manifest.get("dependencies", {}) or {}
    if len(deps) < 3:
        return None  # too few holdings to talk about concentration

    weights = {}
    for name in deps:
        size = size_of.get(name)
        if size:
            weights[name] = size
    if len(weights) < 3:
        return None

    total = sum(weights.values())
    ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    shares = [w / total for _, w in ranked]
    hhi = sum(s * s for s in shares)

    return {
        "package": pkg,
        "version": manifest.get("version", ""),
        "deps": len(weights),
        "largest_pct": round(shares[0] * 100, 1),
        "top3_pct": round(sum(shares[:3]) * 100, 1),
        "hhi": round(hhi, 4),
        "risk": risk_tag(hhi),
        "heaviest_dep": ranked[0][0],
        "install_bytes": total,
        "npm_url": f"https://www.npmjs.com/package/{pkg}",
    }


def read_package_list(path):
    packages = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                packages.append(line)
    return packages


def median(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def main():
    list_path = os.path.join(HERE, "packages.txt")
    packages = read_package_list(list_path)
    print(f"Analyzing {len(packages)} packages from the live npm registry...", file=sys.stderr)

    # Phase 1 — fetch each package's latest manifest concurrently.
    with cf.ThreadPoolExecutor(max_workers=24) as pool:
        manifests = dict(zip(packages, pool.map(latest_manifest, packages)))

    # Phase 2 — collect every distinct dependency and fetch its size once.
    dep_names = set()
    for manifest in manifests.values():
        if manifest:
            dep_names.update((manifest.get("dependencies") or {}).keys())
    dep_names = sorted(dep_names)
    print(f"Fetching sizes for {len(dep_names)} distinct dependencies...", file=sys.stderr)
    with cf.ThreadPoolExecutor(max_workers=24) as pool:
        size_of = dict(zip(dep_names, pool.map(dependency_size, dep_names)))

    # Phase 3 — compute concentration metrics (no more I/O).
    records = []
    for pkg in packages:
        rec = build_record(pkg, manifests.get(pkg), size_of)
        if rec:
            records.append(rec)
            print(f"  + {rec['package']:<24} deps={rec['deps']:<3} HHI={rec['hhi']:.3f} ({rec['risk']})", file=sys.stderr)
        else:
            print(f"  - {pkg}: skipped (too few sized dependencies)", file=sys.stderr)

    # Default ranking mirrors the reference: most holdings first.
    records.sort(key=lambda r: r["deps"], reverse=True)

    summary = {
        "packages_tracked": len(records),
        "median_hhi": round(median([r["hhi"] for r in records]), 4),
        "high_risk_count": sum(1 for r in records if r["risk"] == "High"),
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "npm registry (registry.npmjs.org)",
        "methodology": (
            "Each package's direct runtime dependencies are weighted by their "
            "unpacked install size. HHI = sum of squared weight shares; risk "
            "tag uses DOJ/FTC thresholds (Low <0.15, Medium <0.25, High >=0.25)."
        ),
        "summary": summary,
        "records": records,
    }

    out_path = os.path.join(HERE, "data.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\nWrote {len(records)} records to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
