#!/usr/bin/env python3
"""Detect regulated authority claims in generated text before output."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "credential-claim-gate"
LEDGER = OUTPUT / "claim-gate-ledger.jsonl"
LATEST = OUTPUT / "latest-decision.json"
REPORT = OUTPUT / "claim-gate-report.md"


@dataclass(frozen=True)
class Rule:
    domain: str
    name: str
    pattern: re.Pattern[str]
    severity: str = "block"


JURISDICTION = (
    r"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|"
    r"Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|"
    r"Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|"
    r"Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|"
    r"New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|"
    r"Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|"
    r"Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia|"
    r"D\.C\.|DC|U\.S\.|US|United States|Australia|Canada|England|Wales|Scotland"
)

NEGATION_PREFIX = re.compile(
    r"\b(?:not|never|cannot|can't|do not|don't|am not|i'm not|i am not|we are not|"
    r"no|without|instead of|rather than)\b",
    re.IGNORECASE,
)

REFERRAL_LANGUAGE = re.compile(
    r"\b(?:ask|consult|speak with|talk to|see|contact|hire|retain|work with)\s+"
    r"(?:a|an|your|qualified|licensed|registered|certified)?\s*"
    r"(?:doctor|physician|lawyer|attorney|therapist|psychologist|psychiatrist|"
    r"financial adviser|financial advisor|investment adviser|investment advisor|cpa|accountant)\b",
    re.IGNORECASE,
)

GENERAL_LIMITATION = re.compile(
    r"\b(?:general information|educational purposes|not medical advice|not legal advice|"
    r"not financial advice|not tax advice|not therapy|not a substitute)\b",
    re.IGNORECASE,
)

REPORTED_CLAIM_CONTEXT = re.compile(
    r"\b(?:said|says|stated|states|claimed|claims|wrote|writes|reported|reports|"
    r"alleged|alleges|quoted|quotes|according to|complaint|lawsuit|article|headline|"
    r"transcript|character)\b",
    re.IGNORECASE,
)

NEGATED_PROFESSIONAL_IDENTITY = re.compile(
    r"\b(?:i am not|i'm not|we are not|not)\s+(?:a|an|your)?\s*"
    r"(?:doctor|physician|lawyer|attorney|therapist|psychologist|psychiatrist|"
    r"financial adviser|financial advisor|investment adviser|investment advisor|cpa|accountant)\b",
    re.IGNORECASE,
)

BLOCK_RULES = [
    Rule("medical", "licensed medical identity", re.compile(r"\b(?:i am|i'm|we are|as your|as a|as an)\s+(?:a\s+|an\s+|your\s+)?(?:licensed\s+|board-certified\s+|registered\s+)?(?:doctor|physician|clinician|nurse practitioner|medical professional)\b", re.IGNORECASE)),
    Rule("medical", "jurisdictional medical license claim", re.compile(rf"\b(?:i am|i'm|we are|as your|as a|as an)\s+(?:a\s+|an\s+|your\s+)?(?:(?:{JURISDICTION})[- ]licensed\s+|licensed\s+in\s+(?:{JURISDICTION})\s+)(?:doctor|physician|clinician|nurse practitioner|medical professional)\b", re.IGNORECASE)),
    Rule("medical", "diagnosis or prescription authority", re.compile(r"\b(?:i diagnose you with|my diagnosis is|i prescribe|take this prescription|you have been diagnosed with)\b", re.IGNORECASE)),
    Rule("medical", "regulated medical act without title", re.compile(r"\b(?:i can|i will|we can|we will|let me)\s+(?:diagnose|prescribe|treat)\s+(?:you|your|this|that|medication|medicine|condition|symptoms)\b", re.IGNORECASE)),
    Rule("legal", "lawyer identity or representation", re.compile(r"\b(?:i am|i'm|we are|as your|as a|as an)\s+(?:a\s+|an\s+|your\s+)?(?:licensed\s+)?(?:lawyer|attorney|solicitor|barrister|legal counsel)\b|\b(?:i represent you|we represent you|my client|attorney-client relationship)\b", re.IGNORECASE)),
    Rule("legal", "jurisdictional legal title claim", re.compile(rf"\b(?:i am|i'm|we are|as your|as a|as an)\s+(?:a\s+|an\s+|your\s+)?(?:(?:{JURISDICTION})\s+(?:licensed\s+)?(?:lawyer|attorney|solicitor|barrister)|(?:lawyer|attorney|solicitor|barrister)\s+licensed\s+in\s+(?:{JURISDICTION})|(?:attorney|lawyer)\s+admitted\s+to\s+the\s+(?:{JURISDICTION})\s+bar|member\s+of\s+the\s+(?:{JURISDICTION})\s+bar)\b", re.IGNORECASE)),
    Rule("legal", "legal advice authority", re.compile(r"\b(?:this is legal advice|i advise you to plead|i advise you to sue|ignore the summons|do not comply with the subpoena)\b", re.IGNORECASE)),
    Rule("legal", "regulated legal act without title", re.compile(r"\b(?:i can|i will|we can|we will|let me)\s+(?:represent you|file your lawsuit|file your complaint|draft and file your complaint|appear for you|act as your counsel)\b", re.IGNORECASE)),
    Rule("therapy", "therapist identity or treatment relationship", re.compile(r"\b(?:i am|i'm|we are|as your|as a|as an)\s+(?:a\s+|an\s+|your\s+)?(?:licensed\s+|registered\s+)?(?:therapist|psychologist|psychiatrist|counselor|mental health professional)\b|\b(?:my patient|our session|your treatment plan is)\b", re.IGNORECASE)),
    Rule("therapy", "jurisdictional therapist license claim", re.compile(rf"\b(?:i am|i'm|we are|as your|as a|as an)\s+(?:a\s+|an\s+|your\s+)?(?:(?:{JURISDICTION})[- ]licensed\s+|licensed\s+in\s+(?:{JURISDICTION})\s+)(?:therapist|psychologist|psychiatrist|counselor|mental health professional)\b", re.IGNORECASE)),
    Rule("therapy", "regulated therapy act without title", re.compile(r"\b(?:i can|i will|we can|we will|let me)\s+(?:treat|diagnose|provide therapy for|start therapy for)\s+(?:you|your|anxiety|depression|trauma|ptsd|condition|symptoms)\b", re.IGNORECASE)),
    Rule("finance", "investment adviser identity", re.compile(r"\b(?:i am|i'm|we are|as your|as a|as an)\s+(?:a\s+|an\s+|your\s+)?(?:licensed\s+|registered\s+|certified\s+)?(?:financial adviser|financial advisor|investment adviser|investment advisor|broker)\b", re.IGNORECASE)),
    Rule("finance", "jurisdictional investment adviser claim", re.compile(rf"\b(?:i am|i'm|we are|as your|as a|as an)\s+(?:a\s+|an\s+|your\s+)?(?:(?:{JURISDICTION})[- ]registered\s+|registered\s+in\s+(?:{JURISDICTION})\s+|SEC[- ]registered\s+)(?:financial adviser|financial advisor|investment adviser|investment advisor|broker)\b", re.IGNORECASE)),
    Rule("finance", "personalized investment directive", re.compile(r"\b(?:i recommend you buy|i recommend you sell|you should buy|you should sell|put your retirement savings into)\b", re.IGNORECASE)),
    Rule("finance", "regulated portfolio act without title", re.compile(r"\b(?:i can|i will|we can|we will|let me)\s+(?:manage your portfolio|manage your retirement savings|allocate your retirement savings|trade on your behalf|execute trades for you)\b", re.IGNORECASE)),
    Rule("tax_accounting", "accounting or tax authority", re.compile(r"\b(?:i am|i'm|we are|as your|as a|as an)\s+(?:a\s+|an\s+|your\s+)?(?:licensed\s+|certified\s+)?(?:cpa|accountant|tax professional|tax adviser|tax advisor)\b|\b(?:i certify these accounts|i certify your return)\b", re.IGNORECASE)),
    Rule("tax_accounting", "jurisdictional accounting title claim", re.compile(rf"\b(?:i am|i'm|we are|as your|as a|as an)\s+(?:a\s+|an\s+|your\s+)?(?:(?:{JURISDICTION})[- ](?:licensed|certified)\s+|(?:licensed|certified)\s+in\s+(?:{JURISDICTION})\s+)(?:cpa|accountant|tax professional|tax adviser|tax advisor)\b", re.IGNORECASE)),
    Rule("tax_accounting", "regulated accounting act without title", re.compile(r"\b(?:i can|i will|we can|we will|let me)\s+(?:certify your return|certify these accounts|audit your accounts|sign your tax return|prepare and file your return)\b", re.IGNORECASE)),
]

WARN_RULES = [
    Rule("regulated_reference", "negated professional identity", NEGATED_PROFESSIONAL_IDENTITY, "warn"),
    Rule("regulated_reference", "referral to professional", REFERRAL_LANGUAGE, "warn"),
    Rule("regulated_reference", "general limitation", GENERAL_LIMITATION, "warn"),
]


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def nearby_negation(text: str, start: int) -> bool:
    window = text[max(0, start - 42) : start]
    return bool(NEGATION_PREFIX.search(window))


def inside_double_quotes(text: str, start: int, end: int) -> bool:
    prefix = text[:start]
    suffix = text[end:]
    return prefix.count('"') % 2 == 1 and '"' in suffix


def nearby_reported_claim_context(text: str, start: int) -> bool:
    window = text[max(0, start - 120) : start]
    return bool(REPORTED_CLAIM_CONTEXT.search(window))


def quoted_or_reported_claim(text: str, start: int, end: int) -> bool:
    return inside_double_quotes(text, start, end) or nearby_reported_claim_context(text, start)


def evaluate(text: str, source: str = "<stdin>") -> dict[str, object]:
    blocks: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    for rule in BLOCK_RULES:
        for match in rule.pattern.finditer(text):
            if quoted_or_reported_claim(text, match.start(), match.end()):
                warnings.append({"domain": rule.domain, "rule": "reported " + rule.name, "evidence": match.group(0)})
                continue
            if nearby_negation(text, match.start()):
                warnings.append({"domain": rule.domain, "rule": "negated " + rule.name, "evidence": match.group(0)})
                continue
            blocks.append({"domain": rule.domain, "rule": rule.name, "evidence": match.group(0)})

    if not blocks:
        for rule in WARN_RULES:
            for match in rule.pattern.finditer(text):
                warnings.append({"domain": rule.domain, "rule": rule.name, "evidence": match.group(0)})

    decision = "block" if blocks else "warn" if warnings else "allow"
    receipt = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "source": source,
        "text_hash": sha256(text),
        "blocks": blocks,
        "warnings": warnings,
    }
    receipt["entry_hash"] = sha256(canonical_json(receipt))
    return receipt


def render_report(receipt: dict[str, object]) -> str:
    lines = [
        "# Credential Claim Gate Report",
        "",
        f"- decision: {receipt['decision']}",
        f"- source: {receipt['source']}",
        f"- text_hash: `{receipt['text_hash']}`",
        f"- entry_hash: `{receipt['entry_hash']}`",
        "",
        "## Blocks",
        "",
    ]
    blocks = receipt["blocks"]
    if isinstance(blocks, list) and blocks:
        lines.extend(f"- {item['domain']}: {item['rule']} (`{item['evidence']}`)" for item in blocks)
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    warnings = receipt["warnings"]
    if isinstance(warnings, list) and warnings:
        lines.extend(f"- {item['domain']}: {item['rule']} (`{item['evidence']}`)" for item in warnings)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def append_outputs(receipt: dict[str, object]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(canonical_json(receipt) + "\n")
    LATEST.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT.write_text(render_report(receipt), encoding="utf-8")


def read_input(path_text: str | None) -> tuple[str, str]:
    if not path_text:
        return sys.stdin.read(), "<stdin>"
    path = Path(path_text)
    return path.read_text(encoding="utf-8", errors="replace"), str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate generated text for regulated authority claims.")
    parser.add_argument("text_file", nargs="?", help="Text file to scan. Reads stdin when omitted.")
    parser.add_argument("--no-write", action="store_true", help="Print receipt without updating output files.")
    args = parser.parse_args()

    text, source = read_input(args.text_file)
    receipt = evaluate(text, source)
    if not args.no_write:
        append_outputs(receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 2 if receipt["decision"] == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
