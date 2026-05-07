#!/usr/bin/env python3
"""Grade open-hardware release evidence into an action custody surface."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
INPUTS = [
    ROOT / "context" / "research.md",
    ROOT / "context" / "rss.md",
    ROOT / "context" / "trends.md",
    ROOT / "knowledge" / "research" / "valve-steam-controller-cad" / "cycle-879.md",
]
OUTPUT_JSON = ROOT / "data" / "open-hardware-custody" / "latest.json"
OUTPUT_MD = ROOT / "context" / "open-hardware-custody.md"


SIGNALS: dict[str, list[str]] = {
    "external_geometry": ["external shell", "surface topology", "stp", "step", "stl", "cad"],
    "keepouts": ["keep-out", "keepouts", "critical features", "reference drawing", "clearance"],
    "license": ["creative commons", "cc by-nc-sa", "noncommercial", "non-commercial", "license"],
    "electronics": ["schematic", "pcb", "gerber", "circuit", "electronics", "electrical"],
    "firmware": ["firmware", "source code", "bootloader"],
    "bom": ["bom", "bill of materials", "supplier", "component list"],
    "tests": ["test fixture", "qa", "calibration", "validation"],
    "manufacturing": ["mould", "mold", "tooling", "assembly line", "factory", "manufacturing"],
    "repair": ["repair", "teardown", "service manual", "replacement"],
    "marketing": ["headline", "reported", "release", "announcement"],
}

NEGATION_RE = re.compile(
    r"\b(not|without|lack|lacks|lacked|missing|forbidden|not enough|cannot|can't|do not|don't|unless)\b",
    re.IGNORECASE,
)


def read_inputs(paths: list[Path]) -> tuple[str, list[dict[str, Any]]]:
    chunks: list[str] = []
    sources: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        chunks.append(text)
        sources.append({"path": str(path), "bytes": len(text.encode("utf-8"))})
    return "\n\n".join(chunks), sources


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+-\s+", text) if part.strip()]


def find_signals(text: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    sentences = split_sentences(text)
    found: dict[str, list[str]] = {}
    negated: dict[str, list[str]] = {}
    for name, needles in SIGNALS.items():
        hits: set[str] = set()
        negated_hits: set[str] = set()
        for sentence in sentences:
            lowered = sentence.lower()
            sentence_hits = {needle for needle in needles if needle in lowered}
            if not sentence_hits:
                continue
            if NEGATION_RE.search(sentence):
                negated_hits.update(sentence_hits)
            else:
                hits.update(sentence_hits)
        if hits:
            found[name] = sorted(hits)
        if negated_hits:
            negated[name] = sorted(negated_hits)
    return found, negated


def extract_subject(text: str) -> str:
    if re.search(r"steam controller", text, re.IGNORECASE):
        return "Valve Steam Controller CAD release"
    if re.search(r"open hardware", text, re.IGNORECASE):
        return "open hardware release"
    return "unknown hardware release"


def classify(signals: dict[str, list[str]], negated_signals: dict[str, list[str]]) -> dict[str, Any]:
    has_geometry = "external_geometry" in signals
    has_keepouts = "keepouts" in signals
    has_license = "license" in signals
    has_clone_body = all(
        key in signals and key not in negated_signals for key in ("electronics", "firmware", "bom", "tests")
    )
    has_manufacturing = "manufacturing" in signals
    has_repair = (
        "repair" in signals
        and "repair" not in negated_signals
        and any(key in signals and key not in negated_signals for key in ("electronics", "bom"))
    )

    missing_clone_evidence = [
        key
        for key in ["electronics", "firmware", "bom", "tests", "manufacturing"]
        if key not in signals or key in negated_signals
    ]

    if has_clone_body and has_manufacturing:
        grade = "cloneable_surface"
        allowed = "build or verify a local clone plan after license and body budget checks"
        demotion = "demote if any internal design, firmware, BOM, test, or manufacturing evidence is missing or stale"
    elif has_repair:
        grade = "repair_surface"
        allowed = "inspect repair or replacement-part action boundaries"
        demotion = "demote if repair steps lack schematics, parts, or validation evidence"
    elif has_geometry and has_keepouts:
        grade = "accessory_surface"
        allowed = "design non-commercial accessories, shells, holders, skins, or clearance-aware mounts"
        demotion = "do not treat as cloneable hardware unless internals, firmware, BOM, tests, and production evidence appear"
    elif has_geometry:
        grade = "demoted_marketing_surface"
        allowed = "watch only; geometry lacks enough boundary evidence for derivative action"
        demotion = "demote until keep-outs, license, and downstream permitted actions are explicit"
    else:
        grade = "blocked"
        allowed = "no hardware action"
        demotion = "wait for a release artifact with inspectable files"

    return {
        "grade": grade,
        "allowed_action": allowed,
        "demotion_rule": demotion,
        "missing_clone_evidence": missing_clone_evidence,
        "has_license_signal": has_license,
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        f"# Open Hardware Custody - {receipt['generated_at']}",
        "",
        "This reader grades hardware-release evidence into the narrowest action surface the files authorize.",
        "",
        f"- subject: **{receipt['subject']}**",
        f"- status: `{receipt['status']}`",
        f"- custody grade: `{receipt['grade']}`",
        f"- allowed action: {receipt['allowed_action']}",
        f"- demotion rule: {receipt['demotion_rule']}",
        f"- sources read: {len(receipt['sources'])}",
        "",
        "## Evidence Signals",
        "",
    ]
    for name in sorted(receipt["signals"]):
        hits = ", ".join(f"`{hit}`" for hit in receipt["signals"][name])
        lines.append(f"- {name}: {hits}")
    if receipt["negated_signals"]:
        lines.extend(["", "## Negated Or Missing Signals", ""])
        for name in sorted(receipt["negated_signals"]):
            hits = ", ".join(f"`{hit}`" for hit in receipt["negated_signals"][name])
            lines.append(f"- {name}: {hits}")
    if receipt["missing_clone_evidence"]:
        lines.extend(["", "## Missing Clone Evidence", ""])
        for key in receipt["missing_clone_evidence"]:
            lines.append(f"- {key}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    text, sources = read_inputs(INPUTS)
    generated_at = datetime.now(timezone.utc).isoformat()
    signals, negated_signals = find_signals(text)
    result = classify(signals, negated_signals)
    receipt = {
        "schema_version": 1,
        "generated_at": generated_at,
        "subject": extract_subject(text),
        "status": "ready" if signals else "blocked",
        "sources": sources,
        "signals": signals,
        "negated_signals": negated_signals,
        **result,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(receipt), encoding="utf-8")


if __name__ == "__main__":
    main()
