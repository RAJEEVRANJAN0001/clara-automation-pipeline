#!/usr/bin/env python3
"""
run_pipeline.py — Master orchestrator for the Clara Automation Pipeline.

Pipelines:
  A: Demo calls      -> v1 memo + agent spec
  B: Onboarding calls -> v2 memo + agent spec + changelog

Usage:
    python scripts/run_pipeline.py               # all 5 accounts
    python scripts/run_pipeline.py --account acc_001
    python scripts/run_pipeline.py --validate    # also validate outputs after run
    python scripts/run_pipeline.py --dashboard   # also open dashboard after run
"""

import argparse
import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from config import ACCOUNT_MAP, Colors, DATASET_DIR, OUTPUTS_DIR, CHANGELOG_DIR
from extract_account_info import extract_account_info
from generate_agent_spec import generate_agent_spec
from update_account import extract_onboarding_updates, apply_updates, generate_changelog
from task_tracker import record_pipeline_start, record_pipeline_complete


# ──────────────────────────────────────────────────────────────────────────────
# Logging helpers
# ──────────────────────────────────────────────────────────────────────────────

_LEVEL_COLORS = {
    "INFO": Colors.CYAN,
    "OK": Colors.GREEN,
    "WARN": Colors.YELLOW,
    "ERROR": Colors.RED,
    "STEP": Colors.BOLD + Colors.BLUE,
    "HEAD": Colors.BOLD + Colors.MAGENTA,
}


def log(msg: str, level: str = "INFO") -> None:
    ts = time.strftime("%H:%M:%S")
    c = _LEVEL_COLORS.get(level, "")
    print(f"{c}[{ts}][{level:5s}]{Colors.RESET} {msg}")


def divider(char: str = "-", width: int = 62) -> None:
    print(Colors.BOLD + char * width + Colors.RESET)


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline A: Demo -> v1
# ──────────────────────────────────────────────────────────────────────────────

def run_pipeline_a(account_id: str, demo_path: str, output_dir: str) -> dict:
    """Demo Call -> v1 Memo + Agent Spec. Returns the v1 memo."""
    t0 = time.time()
    log(f"Pipeline A  [{account_id}]", "STEP")

    with open(demo_path, encoding="utf-8") as fh:
        transcript = fh.read()
    log(f"  Read {len(transcript):,} chars")

    record_pipeline_start(account_id, "A")

    memo = extract_account_info(transcript, account_id)
    company = memo.get("company_name") or account_id
    confidence = memo.get("extraction_confidence", {})
    avg_conf = (sum(confidence.values()) / len(confidence)) if confidence else None
    conf_str = f"  (avg confidence {avg_conf:.0f}%)" if avg_conf is not None else ""
    log(f"  Company: {Colors.BOLD}{company}{Colors.RESET}{conf_str}")

    v1_dir = os.path.join(output_dir, "accounts", account_id, "v1")
    os.makedirs(v1_dir, exist_ok=True)

    memo_path = os.path.join(v1_dir, "memo.json")
    with open(memo_path, "w", encoding="utf-8") as fh:
        json.dump(memo, fh, indent=2)
    log(f"  Saved memo     -> {os.path.relpath(memo_path)}")

    agent_spec = generate_agent_spec(memo, "v1")
    spec_path = os.path.join(v1_dir, "agent_spec.json")
    with open(spec_path, "w", encoding="utf-8") as fh:
        json.dump(agent_spec, fh, indent=2)
    log(f"  Saved spec     -> {os.path.relpath(spec_path)}")

    log(f"  {Colors.GREEN}Done{Colors.RESET} ({time.time() - t0:.2f}s)", "OK")
    record_pipeline_complete(account_id, "A")
    return memo


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline B: Onboarding -> v2
# ──────────────────────────────────────────────────────────────────────────────

def run_pipeline_b(
    account_id: str,
    onboarding_path: str,
    v1_memo: dict,
    output_dir: str,
    changelog_dir: str,
) -> tuple:
    """Onboarding Call -> v2 Memo + Agent Spec + Changelog. Returns (v2_memo, changes_count)."""
    t0 = time.time()
    log(f"Pipeline B  [{account_id}]", "STEP")

    with open(onboarding_path, encoding="utf-8") as fh:
        transcript = fh.read()
    log(f"  Read {len(transcript):,} chars")

    record_pipeline_start(account_id, "B")

    updates = extract_onboarding_updates(transcript)
    log(f"  Found {len(updates)} update categories")

    v2_memo, changes = apply_updates(v1_memo, updates)
    log(f"  Applied {Colors.BOLD}{len(changes)}{Colors.RESET} changes")

    v2_dir = os.path.join(output_dir, "accounts", account_id, "v2")
    os.makedirs(v2_dir, exist_ok=True)

    memo_path = os.path.join(v2_dir, "memo.json")
    with open(memo_path, "w", encoding="utf-8") as fh:
        json.dump(v2_memo, fh, indent=2)
    log(f"  Saved v2 memo  -> {os.path.relpath(memo_path)}")

    agent_spec = generate_agent_spec(v2_memo, "v2")
    spec_path = os.path.join(v2_dir, "agent_spec.json")
    with open(spec_path, "w", encoding="utf-8") as fh:
        json.dump(agent_spec, fh, indent=2)
    log(f"  Saved v2 spec  -> {os.path.relpath(spec_path)}")

    os.makedirs(changelog_dir, exist_ok=True)
    changelog = generate_changelog(account_id, changes)
    cl_path = os.path.join(changelog_dir, f"{account_id}_changes.md")
    with open(cl_path, "w", encoding="utf-8") as fh:
        fh.write(changelog)
    log(f"  Saved changelog -> {os.path.relpath(cl_path)}")

    log(f"  {Colors.GREEN}Done{Colors.RESET} ({time.time() - t0:.2f}s)", "OK")
    record_pipeline_complete(account_id, "B")
    return v2_memo, len(changes)


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────

def print_summary(results: dict, total_elapsed: float) -> None:
    """Print a colored table summarising all processed accounts."""
    print()
    divider("=")
    print(f"{Colors.BOLD}  PIPELINE EXECUTION SUMMARY{Colors.RESET}")
    divider("=")

    ok_str = f"{Colors.GREEN}OK  {Colors.RESET}"
    bad_str = f"{Colors.RED}FAIL{Colors.RESET}"

    for account_id, info in results.items():
        pa = ok_str if info.get("pipeline_a") else bad_str
        pb = ok_str if info.get("pipeline_b") else bad_str
        changes = info.get("changes_count", 0)
        company = info.get("company", account_id)
        print(f"  {Colors.BOLD}{account_id}{Colors.RESET}  {company}")
        print(f"    A: Demo -> v1        [{pa}]")
        print(f"    B: Onboarding -> v2  [{pb}]  ({changes} changes)")
        print()

    divider()
    good = sum(1 for v in results.values() if v.get("pipeline_a") and v.get("pipeline_b"))
    total = len(results)
    c = Colors.GREEN if good == total else Colors.YELLOW
    print(f"  {c}{good}/{total} accounts fully processed{Colors.RESET}  ({total_elapsed:.2f}s total)")
    divider("=")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Clara Automation Pipeline end-to-end."
    )
    parser.add_argument("--dataset-dir", default=None,
                        help="Override dataset directory (default: from config)")
    parser.add_argument("--output-dir", default=None,
                        help="Override output directory (default: from config)")
    parser.add_argument("--changelog-dir", default=None,
                        help="Override changelog directory (default: from config)")
    parser.add_argument("--account", default=None,
                        help="Process a single account, e.g. acc_001")
    parser.add_argument("--validate", action="store_true",
                        help="Run validate.py after pipeline completes")
    parser.add_argument("--dashboard", action="store_true",
                        help="Open dashboard.html after pipeline completes")
    args = parser.parse_args()

    dataset_dir   = args.dataset_dir   or DATASET_DIR
    output_dir    = args.output_dir    or OUTPUTS_DIR
    changelog_dir = args.changelog_dir or CHANGELOG_DIR

    divider("=")
    print(f"{Colors.BOLD + Colors.MAGENTA}  Clara Automation Pipeline  v2.0{Colors.RESET}")
    divider("=")
    log(f"Dataset:   {dataset_dir}")
    log(f"Outputs:   {output_dir}")
    log(f"Changelog: {changelog_dir}")

    accounts_to_process = dict(ACCOUNT_MAP)
    if args.account:
        if args.account not in ACCOUNT_MAP:
            log(f"Unknown account: {args.account}. Valid: {list(ACCOUNT_MAP.keys())}", "ERROR")
            sys.exit(1)
        accounts_to_process = {args.account: ACCOUNT_MAP[args.account]}

    results = {}
    global_start = time.time()

    for account_id, info in accounts_to_process.items():
        print()
        divider()
        log(f"{account_id}  -  {info['company']}", "HEAD")
        divider()

        result = {"company": info["company"]}

        # Pipeline A
        demo_path = os.path.join(dataset_dir, "demo_calls", info["demo_file"])
        if not os.path.exists(demo_path):
            log(f"Demo file not found: {demo_path}", "WARN")
            result["pipeline_a"] = False
            results[account_id] = result
            continue
        try:
            v1_memo = run_pipeline_a(account_id, demo_path, output_dir)
            result["pipeline_a"] = True
        except Exception as exc:
            log(f"Pipeline A failed: {exc}", "ERROR")
            result["pipeline_a"] = False
            results[account_id] = result
            continue

        # Pipeline B
        onboarding_path = os.path.join(
            dataset_dir, "onboarding_calls", info["onboarding_file"]
        )
        if not os.path.exists(onboarding_path):
            log(f"Onboarding file not found: {onboarding_path}", "WARN")
            result["pipeline_b"] = False
            result["changes_count"] = 0
        else:
            try:
                _, changes_count = run_pipeline_b(
                    account_id, onboarding_path, v1_memo, output_dir, changelog_dir
                )
                result["pipeline_b"] = True
                result["changes_count"] = changes_count
            except Exception as exc:
                log(f"Pipeline B failed: {exc}", "ERROR")
                result["pipeline_b"] = False
                result["changes_count"] = 0

        results[account_id] = result

    print_summary(results, time.time() - global_start)

    # Optional post-steps
    if args.validate:
        log("Running validation ...", "HEAD")
        subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "validate.py"), "--verbose"])

    if args.dashboard:
        log("Opening dashboard ...", "HEAD")
        subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "dashboard.py"), "--open"])

    # Update task tracker HTML
    subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "task_tracker.py"), "--export-html"])

    failed = [k for k, v in results.items() if not v.get("pipeline_a") or not v.get("pipeline_b")]
    if failed:
        log(f"Failed: {', '.join(failed)}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
