"""Session 5 answer keys and checkers (Exercise A design, coverage, diagnosis drill)."""
import re

from research_corpus import DRIVERS

# Words that show a final report actually covers each driver (case-insensitive).
DRIVER_KEYWORDS = {
    "product_quality": ["tp-0726", "pole"],
    "size_fit": ["size chart", "runs small", "sizing"],
    "shipping_damage": ["swiftship", "damaged in transit", "carrier"],
    "listing_accuracy": ["photo", "not as described", "olive"],
    "returns_policy": ["free return", "return shipping", "changed mind"],
}


def coverage_report(report_text: str, show: bool = True) -> dict:
    """Which of the five ground-truth drivers does a final report cover?"""
    low = (report_text or "").lower()
    covered = {d: any(k in low for k in kws) for d, kws in DRIVER_KEYWORDS.items()}
    cited = sorted(set(re.findall(r"\b(W\d|NW-[A-Z0-9-]+|DS-RET-2026)\b", report_text or "")))
    if show:
        print(f"Drivers covered: {sum(covered.values())}/5")
        for d, ok in covered.items():
            print(f"  [{'x' if ok else ' '}] {d:<17} {DRIVERS[d]}")
        print("Source ids cited:", ", ".join(cited) or "none")
    return {"covered": covered, "n_covered": sum(covered.values()), "cited": cited}


# ---------------------------------------------------------------- Exercise A
DESIGN_KEY = {
    "subagents": "At least 2 specialists split by SOURCE TYPE (web / internal docs / returns data), not by product category.",
    "tools_per_agent": "Each subagent gets only its own source's tools; the coordinator gets only the delegation tool.",
    "context_passed": "The overall question, the period (Q3 vs Q2 2026), the company facts that matter (SwiftShip), "
                      "and for follow-ups, the earlier findings with source ids.",
    "output_format": "Structured report: findings (claim + evidence) separate from source metadata (id, type, date, locator), "
                     "plus status, coverage and gaps.",
    "parallel_or_sequential": "Round 1 parallel (independent sources). Follow-ups sequential only when they need round-1 findings.",
    "refinement": "Coordinator checks coverage criteria against findings, re-delegates for gaps, then re-synthesizes.",
}


def review_design(design: dict) -> None:
    """Print the learner's Exercise A design next to the key, field by field."""
    for field, key in DESIGN_KEY.items():
        mine = str(design.get(field, "")).strip() or "(blank)"
        print(f"{field}\n   yours: {mine}\n   key:   {key}\n")
    agents = str(design.get("subagents", "")).lower()
    if any(w in agents for w in ("tent", "stove", "sleeping")):
        print("Warning: your split is by product category. That is the narrow decomposition from sample Q7.")


# ---------------------------------------------------------------- diagnosis drill
DIAGNOSIS_KEY = "B"
DIAGNOSIS_EXPLANATION = (
    "B. All three subagents returned status 'complete' with accurate findings, so the subagents worked. "
    "The coordinator only ever asked about product quality in three product categories, so shipping, sizing, "
    "listing and policy were never assigned. Root cause: the decomposition (here forced by a procedural, "
    "assumption-laden coordinator prompt). A: more searches would still be about quality. C: the synthesis "
    "faithfully combined what it got. D: no sources were blocked."
)

EXAM_ANSWERS = {"Q1": "C", "Q2": "B", "Q3": "D", "Q4": "A", "Q5": "B"}
