#!/usr/bin/env python3
"""
Build data.json for the Quantum Technology Companies dashboard.

Reads the curated, pipe-delimited companies.csv (the source of truth) and
derives a few analytical fields, then writes data.json for the web UI.

Derived per company:
    * years_active   - years since founding
    * capital_per_yr - total raised / years active (funding velocity, $M/yr)
    * tier           - funding tier used for the colored badge:
                         Mega     >= $500M raised
                         Major    >= $100M raised
                         Emerging <  $100M (or undisclosed)

The figures themselves are compiled from public reporting (see companies.csv);
this script does no network I/O, so the dashboard is reproducible offline.
Edit companies.csv and re-run to update.
"""

import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_YEAR = 2026

FIELDS = [
    "name", "domain", "focus", "stage", "founded",
    "hq", "total_raised_musd", "valuation_musd", "url",
]

# Funding-tier thresholds, in $M raised.
TIER_MEGA = 500
TIER_MAJOR = 100


def parse_int(value):
    value = (value or "").strip()
    return int(value) if value else None


def tier_for(raised):
    if raised is None:
        return "Emerging"
    if raised >= TIER_MEGA:
        return "Mega"
    if raised >= TIER_MAJOR:
        return "Major"
    return "Emerging"


def read_companies(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) != len(FIELDS):
                print(f"  ! skipping malformed line: {line!r}", file=sys.stderr)
                continue
            rows.append(dict(zip(FIELDS, (p.strip() for p in parts))))
    return rows


def build_record(row):
    founded = parse_int(row["founded"])
    raised = parse_int(row["total_raised_musd"])
    valuation = parse_int(row["valuation_musd"])
    years = max(SNAPSHOT_YEAR - founded, 1) if founded else None
    velocity = round(raised / years, 1) if (raised and years) else None

    return {
        "name": row["name"],
        "domain": row["domain"],
        "focus": row["focus"],
        "stage": row["stage"],
        "founded": founded,
        "hq": row["hq"],
        "country": row["hq"].split(",")[-1].strip() if row["hq"] else "",
        "raised_musd": raised,
        "valuation_musd": valuation,
        "years_active": years,
        "capital_per_yr_musd": velocity,
        "tier": tier_for(raised),
        "url": row["url"],
    }


def main():
    src = os.path.join(HERE, "companies.csv")
    rows = read_companies(src)
    records = [build_record(r) for r in rows]

    # Default ranking mirrors the reference: biggest first (by capital raised).
    records.sort(key=lambda r: (r["raised_musd"] or 0), reverse=True)

    disclosed = [r["raised_musd"] for r in records if r["raised_musd"]]
    summary = {
        "companies_tracked": len(records),
        "total_raised_busd": round(sum(disclosed) / 1000, 1),
        "publicly_listed": sum(1 for r in records if r["stage"] == "Public"),
        "domains": sorted({r["domain"] for r in records}),
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_year": SNAPSHOT_YEAR,
        "source": "Compiled from public reporting (company announcements, The Quantum Insider, Crunchbase, SEC filings)",
        "methodology": (
            "Capital-raised and valuation figures are approximate, in USD, compiled "
            "from public sources as of mid-2026. Funding tier: Mega >= $500M, "
            "Major >= $100M, Emerging < $100M or undisclosed."
        ),
        "summary": summary,
        "records": records,
    }

    out = os.path.join(HERE, "data.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print(f"Wrote {len(records)} companies to {out}", file=sys.stderr)
    print(
        f"  total disclosed funding: ${summary['total_raised_busd']}B"
        f" | public: {summary['publicly_listed']}"
        f" | domains: {', '.join(summary['domains'])}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
