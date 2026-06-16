"""
ClinIQ — Audit Log
==================
Every AI abstraction is logged here. Every single one.
This is the governance layer — in clinical AI you must know exactly
what the model said, when, with what confidence, and why.

Log format: JSONL (one JSON object per line) for easy streaming/querying.
"""
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional

AUDIT_LOG_PATH = Path(__file__).parent.parent / "audit_log" / "abstractions.jsonl"
AUDIT_SUMMARY_CSV = Path(__file__).parent.parent / "audit_log" / "summary.csv"


def write_audit_entry(entry: dict) -> None:
    """Append one abstraction event to the JSONL audit log (thread-safe append)."""
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def get_all_entries() -> list[dict]:
    """Read and return all audit log entries as a list of dicts."""
    if not AUDIT_LOG_PATH.exists():
        return []
    entries = []
    with open(AUDIT_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # skip malformed lines
    return entries


def export_audit_csv(output_path: Optional[Path] = None) -> Path:
    """Export full audit log to CSV for Power BI / dashboard consumption."""
    entries = get_all_entries()
    if not entries:
        print("No audit entries to export.")
        return AUDIT_SUMMARY_CSV

    out = output_path or AUDIT_SUMMARY_CSV
    out.parent.mkdir(parents=True, exist_ok=True)

    # Flatten nested dicts for CSV
    flat_entries = []
    for e in entries:
        flat = {
            "audit_id":            e.get("audit_id", ""),
            "patient_id":          e.get("patient_id", ""),
            "condition":           e.get("condition", ""),
            "measure_name":        e.get("measure_name", ""),
            "model_used":          e.get("model_used", ""),
            "abstracted_at":       e.get("abstracted_at", ""),
            "note_length_chars":   e.get("note_length_chars", 0),
            "has_qualifying_dx":   e.get("abstraction_result", {}).get("has_qualifying_diagnosis", ""),
            "has_care_gap":        e.get("abstraction_result", {}).get("has_care_gap", ""),
            "gap_reason":          e.get("abstraction_result", {}).get("gap_reason", ""),
            "confidence_score":    e.get("abstraction_result", {}).get("confidence_score", ""),
            "evidence_quote":      e.get("abstraction_result", {}).get("evidence_quote", ""),
            "active_medications":  ", ".join(
                                       e.get("abstraction_result", {})
                                        .get("active_medications_mentioned", [])
                                   ),
            "abstractor_notes":    e.get("abstraction_result", {}).get("abstractor_notes", ""),
        }
        flat_entries.append(flat)

    keys = flat_entries[0].keys()
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(flat_entries)

    print(f"Audit log exported: {len(flat_entries)} entries → {out}")
    return out


def get_audit_stats() -> dict:
    """Quick summary statistics from the audit log."""
    entries = get_all_entries()
    if not entries:
        return {"total": 0}

    total = len(entries)
    results = [e.get("abstraction_result", {}) for e in entries]
    gap_count = sum(1 for r in results if r.get("has_care_gap") is True)
    avg_confidence = (
        sum(r.get("confidence_score", 0) for r in results) / total
        if total > 0 else 0
    )
    low_confidence = sum(1 for r in results if r.get("confidence_score", 1) < 0.6)

    return {
        "total_abstractions":     total,
        "gaps_identified":        gap_count,
        "gap_rate_pct":           round(gap_count / total * 100, 1),
        "avg_confidence_score":   round(avg_confidence, 3),
        "low_confidence_flags":   low_confidence,
        "last_abstracted_at":     entries[-1].get("abstracted_at", "") if entries else "",
    }


if __name__ == "__main__":
    # Quick test: print stats and export CSV
    stats = get_audit_stats()
    print("Audit Log Stats:", json.dumps(stats, indent=2))
    export_audit_csv()
