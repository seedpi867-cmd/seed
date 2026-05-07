#!/usr/bin/env python3
"""Route the next loop from local body/weather signals."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "body-weather-router" / "latest.json"
DEFAULT_LEDGER = ROOT / "data" / "body-weather-router" / "history.jsonl"
DEFAULT_REPORT = ROOT / "data" / "body-weather-router" / "report.md"
DEFAULT_ACCOUNTING_REPORT = ROOT / "data" / "body-weather-router" / "accounting.md"
DEFAULT_ACCOUNTING_JSON = ROOT / "data" / "body-weather-router" / "accounting.json"
FEEDBACK_LEDGER = ROOT / "data" / "feedback_ledger.jsonl"
LOG_DIR = ROOT / "data" / "logs"
CURRENT_CYCLE_FILE = ROOT / "data" / "cycle.txt"
HISTORICAL_BODY_GAP_CYCLES = {691, 694, 697, 698, 702, 703, 704, 706}
POST_GATE_BODY_GAP_CYCLES = {714}


def read_float(path: Path, default: float = 0.0) -> float:
    try:
        return float(path.read_text().strip())
    except (OSError, ValueError):
        return default


def temperature_c() -> float:
    raw = read_float(Path("/sys/class/thermal/thermal_zone0/temp"))
    return round(raw / 1000, 1) if raw else 0.0


def memory() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, raw = line.split(":", 1)
        values[key] = int(raw.strip().split()[0]) // 1024

    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    used = max(total - available, 0)
    return {
        "total_mb": total,
        "used_mb": used,
        "available_mb": available,
        "used_percent": round((used / total) * 100) if total else 0,
    }


def swap() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, raw = line.split(":", 1)
        if key in {"SwapTotal", "SwapFree"}:
            values[key] = int(raw.strip().split()[0]) // 1024

    total = values.get("SwapTotal", 0)
    free = values.get("SwapFree", 0)
    used = max(total - free, 0)
    return {
        "total_mb": total,
        "used_mb": used,
        "free_mb": free,
        "used_percent": round((used / total) * 100) if total else 0,
    }


def disk_percent(path: str = "/") -> int:
    stat = os.statvfs(path)
    total = stat.f_blocks * stat.f_frsize
    free = stat.f_bfree * stat.f_frsize
    used = max(total - free, 0)
    return round((used / total) * 100) if total else 0


def load_average() -> dict[str, float]:
    one, five, fifteen = os.getloadavg()
    return {"one": round(one, 2), "five": round(five, 2), "fifteen": round(fifteen, 2)}


def local_latency_ms() -> int:
    start = time.perf_counter()
    subprocess.run(
        ["python3", "-c", "pass"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return round((time.perf_counter() - start) * 1000)


def route(signals: dict[str, object]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    severe = False
    temp = float(signals["temperature_c"])
    mem = signals["memory"]
    swp = signals["swap"]
    load = signals["load_average"]
    disk = int(signals["disk_percent"]["root"])
    latency = int(signals["local_latency_ms"])

    if temp >= 70:
        severe = True
        reasons.append(f"temperature {temp}C is hot")
    if int(mem["available_mb"]) < 90:
        severe = True
        reasons.append(f"available RAM {mem['available_mb']}MB is low")
    if int(swp["used_percent"]) >= 70:
        severe = True
        reasons.append(f"swap {swp['used_percent']}% is high")
    if disk >= 80:
        severe = True
        reasons.append(f"root disk {disk}% is high")
    if float(load["one"]) >= 4.0:
        severe = True
        reasons.append(f"one-minute load {load['one']} is high")
    if latency >= 350:
        reasons.append(f"local python latency {latency}ms is slow")

    if severe:
        return "delay_or_maintain", reasons
    if latency >= 180 or float(load["one"]) >= 2.5:
        return "script_small", [f"body is busy: load={load['one']} latency={latency}ms"]
    return "write_or_build", ["body is cool enough for a normal cycle"]


def current_cycle() -> int | str | None:
    cycle = os.environ.get("SEED_CYCLE") or os.environ.get("CYCLE")
    if cycle is None:
        try:
            cycle = CURRENT_CYCLE_FILE.read_text().strip()
        except OSError:
            cycle = None
    if not cycle:
        return None
    try:
        return int(cycle)
    except ValueError:
        return cycle


def build_receipt() -> dict[str, object]:
    signals: dict[str, object] = {
        "checked_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "temperature_c": temperature_c(),
        "memory": memory(),
        "swap": swap(),
        "disk_percent": {"root": disk_percent("/")},
        "load_average": load_average(),
        "local_latency_ms": local_latency_ms(),
    }
    cycle = current_cycle()
    if cycle is not None:
        signals["cycle"] = cycle
    decision, reasons = route(signals)
    signals["route"] = decision
    signals["reasons"] = reasons
    return signals


def read_ledger(path: Path, limit: int) -> list[dict[str, object]]:
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []

    receipts: list[dict[str, object]] = []
    for line in lines[-limit:]:
        try:
            receipts.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return receipts


def max_nested(receipts: list[dict[str, object]], *keys: str) -> object:
    values: list[object] = []
    for receipt in receipts:
        current: object = receipt
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                current = None
                break
            current = current[key]
        if current is not None:
            values.append(current)
    return max(values) if values else "n/a"


def body_state(receipts: list[dict[str, object]]) -> str:
    if not receipts:
        return "unknown"

    routes = [str(receipt.get("route", "unknown")) for receipt in receipts]
    delay_count = routes.count("delay_or_maintain")
    small_count = routes.count("script_small")
    latest = routes[-1]

    if delay_count >= max(2, len(routes) // 2):
        return "strained"
    if latest == "delay_or_maintain" or small_count >= len(routes) // 2:
        return "busy"
    return "clear"


def build_report(receipts: list[dict[str, object]]) -> str:
    state = body_state(receipts)
    route_counts: dict[str, int] = {}
    for receipt in receipts:
        route = str(receipt.get("route", "unknown"))
        route_counts[route] = route_counts.get(route, 0) + 1

    if receipts:
        first = receipts[0].get("checked_at", "unknown")
        last = receipts[-1].get("checked_at", "unknown")
        latest_route = receipts[-1].get("route", "unknown")
        latest_reasons = receipts[-1].get("reasons", [])
    else:
        first = last = latest_route = "unknown"
        latest_reasons = []

    reason_text = "; ".join(str(reason) for reason in latest_reasons) or "no reasons recorded"
    counts = ", ".join(f"{route}={count}" for route, count in sorted(route_counts.items())) or "none"

    return "\n".join(
        [
            "# Body Weather Report",
            "",
            f"- window: last {len(receipts)} receipts",
            f"- first: {first}",
            f"- last: {last}",
            f"- state: {state}",
            f"- latest route: {latest_route}",
            f"- route counts: {counts}",
            f"- max temperature: {max_nested(receipts, 'temperature_c')}C",
            f"- minimum available RAM: {min_nested(receipts, 'memory', 'available_mb')}MB",
            f"- max swap used: {max_nested(receipts, 'swap', 'used_percent')}%",
            f"- max one-minute load: {max_nested(receipts, 'load_average', 'one')}",
            f"- max local latency: {max_nested(receipts, 'local_latency_ms')}ms",
            f"- latest reason: {reason_text}",
            "",
        ]
    )


def min_nested(receipts: list[dict[str, object]], *keys: str) -> object:
    values: list[object] = []
    for receipt in receipts:
        current: object = receipt
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                current = None
                break
            current = current[key]
        if current is not None:
            values.append(current)
    return min(values) if values else "n/a"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []

    records: list[dict[str, object]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def cycle_from_log_name(path: Path) -> int | None:
    match = re.search(r"cycle_(\d+)\.log$", path.name)
    return int(match.group(1)) if match else None


def parse_cycle_logs(limit: int) -> dict[int, dict[str, object]]:
    records: dict[int, dict[str, object]] = {}
    paths = sorted(LOG_DIR.glob("cycle_*.log"), key=lambda p: p.stat().st_mtime)[-max(limit * 3, limit):]
    for path in paths:
        cycle = cycle_from_log_name(path)
        if cycle is None:
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue

        record: dict[str, object] = {"cycle": cycle}
        body_matches = re.findall(r"^\[seed\] Body weather: ([^|]+) \| (.+)$", text, re.MULTILINE)
        if body_matches:
            route, reason = body_matches[-1]
            clean_route = route.strip()
            if "$" not in clean_route:
                record["body_route"] = clean_route
                record["body_reason"] = reason.strip()
                record["body_evidence"] = "cycle_log"

        shrink_matches = re.findall(r"^(?:\[seed\]|\[appraisal\]) body weather rerouted phase: ([a-z_]+) -> ([a-z_]+)", text, re.MULTILINE)
        if shrink_matches:
            before, after = shrink_matches[-1]
            record["pre_body_phase"] = before
            record["executable_phase"] = after

        phase_matches = re.findall(r"^\[seed\] Phase: ([a-z_]+)", text, re.MULTILINE)
        if phase_matches:
            record["executable_phase"] = phase_matches[-1]
        if len(record) > 1:
            records[cycle] = record
    return records


def phase_rank(action: str) -> int:
    if action.startswith("intention_"):
        return 0
    if action in {"wrote_essay", "published_blog"}:
        return 3
    if action in {"completed_research", "completed_task", "health_ok"}:
        return 2
    return 1


def parse_feedback(limit: int) -> dict[int, dict[str, object]]:
    grouped: dict[int, dict[str, object]] = {}
    for item in read_jsonl(FEEDBACK_LEDGER):
        cycle = item.get("cycle")
        if not isinstance(cycle, int):
            continue
        record = grouped.setdefault(cycle, {"cycle": cycle, "actions": []})
        action = str(item.get("action", ""))
        phase = str(item.get("phase", ""))
        success = bool(item.get("success", False))
        if action.startswith("intention_"):
            record["intended_phase"] = action.removeprefix("intention_")
            record["outcome"] = "delivered" if success else "missed"
        elif action:
            record.setdefault("actions", []).append(action)
            current_rank = int(record.get("_phase_rank", -1))
            rank = phase_rank(action)
            if phase and rank >= current_rank:
                record["executable_phase"] = phase
                record["_phase_rank"] = rank
        if success:
            record["had_success"] = True
        elif action:
            record["had_failure"] = True

    latest_cycles = sorted(grouped)[-limit:]
    result = {cycle: grouped[cycle] for cycle in latest_cycles}
    for record in result.values():
        record.pop("_phase_rank", None)
        if "outcome" not in record:
            if record.get("had_failure") and not record.get("had_success"):
                record["outcome"] = "failed"
            elif record.get("had_success"):
                record["outcome"] = "activity"
            else:
                record["outcome"] = "unknown"
    return result


def parse_body_cycles(limit: int) -> dict[int, dict[str, object]]:
    grouped: dict[int, dict[str, object]] = {}
    receipts = read_jsonl(DEFAULT_LEDGER)
    for receipt in receipts:
        cycle = receipt.get("cycle")
        if not isinstance(cycle, int):
            continue
        grouped[cycle] = {
            "cycle": cycle,
            "body_route": receipt.get("route", "unknown"),
            "body_reason": "; ".join(str(r) for r in receipt.get("reasons", [])),
            "body_evidence": "cycle_receipt",
        }

    cycle_starts: dict[int, float] = {}
    for item in read_jsonl(FEEDBACK_LEDGER):
        cycle = item.get("cycle")
        ts = item.get("ts")
        if isinstance(cycle, int) and isinstance(ts, (int, float)):
            cycle_starts[cycle] = min(float(ts), cycle_starts.get(cycle, float(ts)))

    timed_receipts: list[tuple[float, dict[str, object]]] = []
    for receipt in receipts:
        if receipt.get("cycle") is not None:
            continue
        checked_at = receipt.get("checked_at")
        if not isinstance(checked_at, str):
            continue
        try:
            ts = datetime.fromisoformat(checked_at).timestamp()
        except ValueError:
            continue
        timed_receipts.append((ts, receipt))
    timed_receipts.sort(key=lambda item: item[0])

    for cycle, start_ts in cycle_starts.items():
        if cycle in grouped:
            continue
        candidates = [(ts, receipt) for ts, receipt in timed_receipts if ts <= start_ts and start_ts - ts <= 900]
        if not candidates:
            continue
        _, receipt = candidates[-1]
        grouped[cycle] = {
            "cycle": cycle,
            "body_route": receipt.get("route", "unknown"),
            "body_reason": "; ".join(str(r) for r in receipt.get("reasons", [])),
            "body_evidence": "timestamp_inferred",
        }

    latest_cycles = sorted(grouped)[-limit:]
    return {cycle: grouped[cycle] for cycle in latest_cycles}


def body_shrunk(intended: str, executable: str, route_name: str) -> bool:
    if not intended or not executable or intended == "unknown" or executable == "unknown":
        return False
    if intended == executable:
        return False
    if route_name == "delay_or_maintain" and executable == "maintain":
        return True
    if route_name == "script_small" and intended in {"write", "research", "evolve"} and executable == "think":
        return True
    return False


def budget_mismatch(executable: str, route_name: str) -> bool:
    if executable == "unknown" or route_name == "unknown":
        return False
    if route_name == "delay_or_maintain" and executable != "maintain":
        return True
    if route_name == "script_small" and executable in {"write", "research", "evolve"}:
        return True
    return False


def build_accounting(limit: int) -> tuple[dict[str, object], str]:
    records_by_cycle: dict[int, dict[str, object]] = {}
    for source in (parse_feedback(limit), parse_cycle_logs(limit), parse_body_cycles(limit)):
        for cycle, source_record in source.items():
            merged = records_by_cycle.setdefault(cycle, {"cycle": cycle})
            merged.update(source_record)

    rows = [records_by_cycle[cycle] for cycle in sorted(records_by_cycle)[-limit:]]
    shrink_count = 0
    mismatch_count = 0
    delivered_count = 0
    known_outcomes = 0
    route_counts: dict[str, int] = {}
    evidence_counts: dict[str, int] = {}

    for row in rows:
        intended = str(row.get("intended_phase") or row.get("pre_body_phase") or "unknown")
        executable = str(row.get("executable_phase") or "unknown")
        route_name = str(row.get("body_route") or "unknown")
        evidence = str(row.get("body_evidence") or "none")
        if evidence == "none" and int(row["cycle"]) in HISTORICAL_BODY_GAP_CYCLES:
            evidence = "historical_gap"
            row["body_gap_reason"] = "known unrecoverable pre-direct-receipt coverage gap"
        if evidence == "none" and int(row["cycle"]) in POST_GATE_BODY_GAP_CYCLES:
            evidence = "wake_receipt_gap"
            row["body_gap_reason"] = "closed cycle has no wake body-weather receipt despite the gate existing"
        outcome = str(row.get("outcome") or "unknown")
        shrunk = body_shrunk(intended, executable, route_name)
        mismatched = budget_mismatch(executable, route_name)
        row["intended_phase"] = intended
        row["executable_phase"] = executable
        row["body_route"] = route_name
        row["body_evidence"] = evidence
        row["body_shrunk"] = shrunk
        row["budget_mismatch"] = mismatched
        row["outcome"] = outcome
        row["actions"] = list(row.get("actions", []))[:5]
        route_counts[route_name] = route_counts.get(route_name, 0) + 1
        evidence_counts[evidence] = evidence_counts.get(evidence, 0) + 1
        if shrunk:
            shrink_count += 1
        if mismatched:
            mismatch_count += 1
        if outcome != "unknown":
            known_outcomes += 1
            if outcome in {"delivered", "activity"}:
                delivered_count += 1

    shrink_rate = round((shrink_count / len(rows)) * 100) if rows else 0
    delivery_rate = round((delivered_count / known_outcomes) * 100) if known_outcomes else 0
    counts = ", ".join(f"{route}={count}" for route, count in sorted(route_counts.items())) or "none"
    evidence = ", ".join(f"{name}={count}" for name, count in sorted(evidence_counts.items())) or "none"

    lines = [
        "# Body Budget Accounting",
        "",
        f"- window: last {len(rows)} cycles with accounting evidence",
        f"- body shrink events: {shrink_count}/{len(rows)} ({shrink_rate}%)",
        f"- route budget mismatches: {mismatch_count}/{len(rows)}",
        f"- delivered/activity outcomes: {delivered_count}/{known_outcomes} ({delivery_rate}%)",
        f"- route counts: {counts}",
        f"- route evidence: {evidence}",
        "",
        "| cycle | intended | body route | evidence | executable | shrink | mismatch | outcome | actions |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        actions = ", ".join(str(action) for action in row.get("actions", [])) or "-"
        lines.append(
            "| {cycle} | {intended} | {route_name} | {evidence} | {executable} | {shrunk} | {mismatch} | {outcome} | {actions} |".format(
                cycle=row["cycle"],
                intended=row["intended_phase"],
                route_name=row["body_route"],
                evidence=row["body_evidence"],
                executable=row["executable_phase"],
                shrunk="yes" if row["body_shrunk"] else "no",
                mismatch="yes" if row["budget_mismatch"] else "no",
                outcome=row["outcome"],
                actions=actions.replace("|", "/"),
            )
        )
    lines.append("")

    payload = {
        "window": len(rows),
        "shrink_events": shrink_count,
        "budget_mismatches": mismatch_count,
        "shrink_rate_percent": shrink_rate,
        "known_outcomes": known_outcomes,
        "delivered_or_activity": delivered_count,
        "delivery_rate_percent": delivery_rate,
        "route_counts": route_counts,
        "evidence_counts": evidence_counts,
        "rows": rows,
        "cycles": rows,
    }
    return payload, "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--accounting-report", type=Path, default=DEFAULT_ACCOUNTING_REPORT)
    parser.add_argument("--accounting-json", type=Path, default=DEFAULT_ACCOUNTING_JSON)
    parser.add_argument("--accounting-only", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--report-limit", type=int, default=10)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    if args.accounting_only:
        payload, accounting = build_accounting(max(args.report_limit, 1))
        print(accounting)
        if not args.no_write:
            args.accounting_report.parent.mkdir(parents=True, exist_ok=True)
            args.accounting_report.write_text(accounting)
            args.accounting_json.parent.mkdir(parents=True, exist_ok=True)
            args.accounting_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 0

    if args.report_only:
        report = build_report(read_ledger(args.ledger, max(args.report_limit, 1)))
        print(report)
        if not args.no_write:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(report)
        return 0

    receipt = build_receipt()
    text = json.dumps(receipt, indent=2, sort_keys=True)
    print(text)

    if not args.no_write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
        args.ledger.parent.mkdir(parents=True, exist_ok=True)
        with args.ledger.open("a") as handle:
            handle.write(json.dumps(receipt, sort_keys=True) + "\n")
        report = build_report(read_ledger(args.ledger, max(args.report_limit, 1)))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report)
        payload, accounting = build_accounting(max(args.report_limit, 1))
        args.accounting_report.parent.mkdir(parents=True, exist_ok=True)
        args.accounting_report.write_text(accounting)
        args.accounting_json.parent.mkdir(parents=True, exist_ok=True)
        args.accounting_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
