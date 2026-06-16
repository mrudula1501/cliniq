"""
ClinIQ AI Abstraction Agent
============================
Reads unstructured clinical notes and abstracts quality measure data.
Every inference is logged to the audit trail with evidence and confidence score.

Built with LangGraph (workflow orchestration) + Claude (Anthropic).

Usage:
  python cliniq_agent.py \\
    --patient_id P12345 \\
    --note "Patient with known HF. On lisinopril. Beta blocker not prescribed." \\
    --condition heart_failure \\
    --measure HF_GDMT_GAP

  # Or batch mode from a CSV of notes:
  python cliniq_agent.py --batch ../data/notes_sample.csv
"""
import os
import sys
import json
import uuid
import argparse
import csv
from pathlib import Path
from datetime import datetime
from typing import TypedDict, Optional

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).parent))
from audit_log import write_audit_entry, get_audit_stats

load_dotenv(Path(__file__).parent.parent / ".env")

# ---------------------------------------------------------------------------
# Load system prompt from file
# ---------------------------------------------------------------------------
PROMPT_PATH = Path(__file__).parent / "prompts" / "abstraction_prompt.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8").strip()

client = Anthropic()


# ---------------------------------------------------------------------------
# LangGraph State
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    patient_id:         str
    clinical_note:      str
    condition:          str
    measure_name:       str
    abstraction_result: dict
    audit_id:           str
    error:              Optional[str]


# ---------------------------------------------------------------------------
# Graph Nodes
# ---------------------------------------------------------------------------
def abstract_note(state: AgentState) -> AgentState:
    """
    Node 1: Call Claude to extract structured quality measure data from the note.
    Returns JSON matching the schema in abstraction_prompt.txt.
    """
    user_message = f"""Patient ID: {state['patient_id']}
Condition: {state['condition']}
Quality Measure: {state['measure_name']}

Clinical Note:
{state['clinical_note']}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = response.content[0].text.strip()

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        result = json.loads(raw_text)
        state["abstraction_result"] = result
        state["error"] = None

    except json.JSONDecodeError as e:
        state["abstraction_result"] = {
            "has_qualifying_diagnosis": None,
            "has_care_gap": None,
            "confidence_score": 0.0,
            "gap_reason": "Parse error — model returned non-JSON",
            "evidence_quote": "",
            "abstractor_notes": f"JSON parse error: {str(e)}",
        }
        state["error"] = f"JSON parse error: {str(e)}"

    except Exception as e:
        state["abstraction_result"] = {
            "has_qualifying_diagnosis": None,
            "has_care_gap": None,
            "confidence_score": 0.0,
            "gap_reason": "API error",
            "evidence_quote": "",
            "abstractor_notes": f"Error: {str(e)}",
        }
        state["error"] = str(e)

    return state


def log_abstraction(state: AgentState) -> AgentState:
    """
    Node 2: Write the abstraction result to the audit trail.
    Every inference is logged — no exceptions.
    """
    audit_entry = {
        "audit_id":           state["audit_id"],
        "patient_id":         state["patient_id"],
        "condition":          state["condition"],
        "measure_name":       state["measure_name"],
        "abstraction_result": state["abstraction_result"],
        "model_used":         "claude-sonnet-4-6",
        "abstracted_at":      datetime.utcnow().isoformat() + "Z",
        "note_length_chars":  len(state["clinical_note"]),
        "error":              state.get("error"),
    }
    write_audit_entry(audit_entry)
    return state


# ---------------------------------------------------------------------------
# Build LangGraph Workflow
# ---------------------------------------------------------------------------
workflow = StateGraph(AgentState)
workflow.add_node("abstract", abstract_note)
workflow.add_node("log",      log_abstraction)
workflow.set_entry_point("abstract")
workflow.add_edge("abstract", "log")
workflow.add_edge("log",      END)
app = workflow.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def run_abstraction(
    patient_id: str,
    note: str,
    condition: str,
    measure: str,
) -> dict:
    """Run a single note through the abstraction workflow."""
    result = app.invoke({
        "patient_id":         patient_id,
        "clinical_note":      note,
        "condition":          condition,
        "measure_name":       measure,
        "abstraction_result": {},
        "audit_id":           str(uuid.uuid4()),
        "error":              None,
    })
    return result["abstraction_result"]


def run_batch(csv_path: str, condition: str, measure: str) -> list[dict]:
    """
    Batch mode: run abstraction on a CSV with columns:
    patient_id, clinical_note
    """
    results = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Abstracting {len(rows)} notes for {condition} / {measure}...")
    for i, row in enumerate(rows, 1):
        pid = row.get("patient_id", f"P{i:05d}")
        note = row.get("clinical_note", "")
        result = run_abstraction(pid, note, condition, measure)
        results.append({"patient_id": pid, **result})
        confidence = result.get("confidence_score", 0)
        gap = result.get("has_care_gap", "?")
        print(f"  [{i}/{len(rows)}] {pid} — gap={gap}, confidence={confidence:.2f}")

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="ClinIQ: Abstract clinical notes for quality measures.")
    parser.add_argument("--patient_id", help="Patient ID for single-note mode")
    parser.add_argument("--note",       help="Clinical note text (single-note mode)")
    parser.add_argument("--condition",  help="Condition name (e.g., heart_failure)")
    parser.add_argument("--measure",    help="Quality measure (e.g., HF_GDMT_GAP)")
    parser.add_argument("--batch",      help="CSV file path for batch mode")
    parser.add_argument("--stats",      action="store_true", help="Print audit log stats and exit")
    args = parser.parse_args()

    if args.stats:
        stats = get_audit_stats()
        print(json.dumps(stats, indent=2))
        return

    if args.batch:
        condition = args.condition or "heart_failure"
        measure = args.measure or "HF_GDMT_GAP"
        results = run_batch(args.batch, condition, measure)
        print(f"\nDone. {len(results)} notes abstracted.")
        print("Audit log stats:", json.dumps(get_audit_stats(), indent=2))
        return

    if not all([args.patient_id, args.note, args.condition, args.measure]):
        parser.error("Single-note mode requires --patient_id, --note, --condition, and --measure")

    print(f"Abstracting note for patient {args.patient_id}...")
    result = run_abstraction(args.patient_id, args.note, args.condition, args.measure)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
