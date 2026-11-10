"""CSV audit trail. Every record a skill touches is written here before any
write. Files land under data/audit-logs/ in the working directory, which is
gitignored because they may contain PII."""

import csv
import os

AUDIT_DIR = os.path.join("data", "audit-logs")


def write_csv(path, rows, fields=None):
    """Write dict rows to `path`, creating directories. Returns the path."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fields = fields or (list(rows[0].keys()) if rows else ["id"])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def audit_path(skill, stage, suffix=""):
    return os.path.join(AUDIT_DIR, f"{skill}-{stage}{suffix}.csv")
