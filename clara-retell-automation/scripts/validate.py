#!/usr/bin/env python3
"""
validate.py — Validate pipeline outputs for schema correctness and completeness.

Checks:
  - All required memo fields are present and non-empty
  - All required agent_spec fields are present
  - Conversation flow nodes are well-formed
  - v2 is an improvement over v1 (has more info)
  - Changelogs are non-empty

Usage:
    python scripts/validate.py               # Validate all accounts
    python scripts/validate.py --account acc_001
    python scripts/validate.py --verbose
"""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import ACCOUNTS_DIR, CHANGELOG_DIR, ACCOUNT_MAP, Colors, REQUIRED_MEMO_FIELDS


# ─── Validation Rules ──────────────────────────────────────────────────────────

def check_memo(memo: dict, version: str, account_id: str) -> list:
    """Return list of (severity, message) issues found in a memo."""
    issues = []

    # Required fields
    for field in REQUIRED_MEMO_FIELDS:
        if field not in memo:
            issues.append(("ERROR", f"{version}/memo.json missing required field: '{field}'"))
        elif not memo[field]:
            # Don't warn about empty questions_or_unknowns if confidence is high
            if field == "questions_or_unknowns":
                overall = memo.get("extraction_confidence", {}).get("overall", 0)
                if overall >= 80:
                    continue  # high-confidence account, empty unknowns is correct
            issues.append(("WARN", f"{version}/memo.json field '{field}' is empty"))

    # account_id consistency
    if memo.get("account_id") and memo["account_id"] != account_id:
        issues.append(("ERROR", f"{version}/memo.json account_id mismatch: '{memo['account_id']}' vs expected '{account_id}'"))

    # Business hours sanity
    hours = memo.get("business_hours", {})
    if hours:
        if not hours.get("days"):
            issues.append(("WARN", f"{version}/memo.json business_hours.days is empty"))
        if not hours.get("start") or not hours.get("end"):
            issues.append(("WARN", f"{version}/memo.json business_hours start/end times missing"))

    # Services
    services = memo.get("services_supported", [])
    if not services:
        issues.append(("WARN", f"{version}/memo.json services_supported is empty"))
    elif len(services) < 3:
        issues.append(("WARN", f"{version}/memo.json only {len(services)} service(s) found — expected more"))

    # Emergency routing
    er = memo.get("emergency_routing_rules", {})
    if not er.get("primary_phone"):
        issues.append(("WARN", f"{version}/memo.json emergency_routing_rules.primary_phone is empty"))

    return issues


def check_agent_spec(spec: dict, version: str) -> list:
    """Return list of issues found in an agent spec."""
    issues = []

    required = ["agent_name", "version", "voice_id", "conversationFlow",
                 "response_engine", "call_transfer_protocol", "fallback_protocol"]
    for field in required:
        if not spec.get(field):
            issues.append(("ERROR", f"{version}/agent_spec.json missing field: '{field}'"))

    # Version tag
    if spec.get("version") != version:
        issues.append(("WARN", f"{version}/agent_spec.json version tag '{spec.get('version')}' doesn't match expected '{version}'"))

    # Conversation flow nodes
    flow = spec.get("conversationFlow", {})
    nodes = flow.get("nodes", [])
    if isinstance(nodes, list) and len(nodes) == 0:
        issues.append(("ERROR", f"{version}/agent_spec.json conversationFlow.nodes is empty"))

    # Check node types present
    node_types = {n.get("type") for n in (nodes if isinstance(nodes, list) else [])}
    for req_type in ("conversation", "extract_dynamic_variables", "branch", "end"):
        if req_type not in node_types:
            issues.append(("WARN", f"{version}/agent_spec.json missing node type: '{req_type}'"))

    # Global prompt length
    prompt = flow.get("global_prompt", "")
    if len(prompt) < 100:
        issues.append(("WARN", f"{version}/agent_spec.json global_prompt is very short ({len(prompt)} chars)"))

    return issues


def check_v2_improvement(v1_memo: dict, v2_memo: dict) -> list:
    """Verify v2 memo is an improvement over v1."""
    issues = []

    v1_services = set(v1_memo.get("services_supported", []))
    v2_services = set(v2_memo.get("services_supported", []))
    if v1_services == v2_services:
        issues.append(("WARN", "v2 memo services_supported unchanged from v1"))

    # Check v2 has different notes / questions_or_unknowns from v1
    v1_notes = v1_memo.get("notes", "")
    v2_notes = v2_memo.get("notes", "")
    if v1_notes == v2_notes and v1_notes:
        issues.append(("WARN", "v2 memo notes identical to v1"))

    return issues


def check_changelog(account_id: str) -> list:
    """Validate changelog exists and is non-trivial."""
    issues = []
    path = os.path.join(CHANGELOG_DIR, f"{account_id}_changes.md")
    if not os.path.exists(path):
        issues.append(("ERROR", f"Changelog missing: changelog/{account_id}_changes.md"))
        return issues
    with open(path) as f:
        content = f.read()
    if len(content.strip()) < 50:
        issues.append(("WARN", f"Changelog for {account_id} is suspiciously short"))
    if "Changes:" not in content and "changes" not in content.lower():
        issues.append(("WARN", f"Changelog for {account_id} doesn't list any changes"))
    return issues


# ─── Per-Account Validation ────────────────────────────────────────────────────

def validate_account(account_id: str, verbose: bool = False) -> dict:
    """Run all checks for a single account. Returns result dict."""
    base = os.path.join(ACCOUNTS_DIR, account_id)
    all_issues = []

    for version in ["v1", "v2"]:
        version_dir = os.path.join(base, version)

        # Check memo
        memo_path = os.path.join(version_dir, "memo.json")
        if not os.path.exists(memo_path):
            all_issues.append(("ERROR", f"{version}/memo.json not found"))
            continue
        with open(memo_path) as f:
            memo = json.load(f)
        all_issues.extend(check_memo(memo, version, account_id))

        # Check agent spec
        spec_path = os.path.join(version_dir, "agent_spec.json")
        if not os.path.exists(spec_path):
            all_issues.append(("ERROR", f"{version}/agent_spec.json not found"))
        else:
            with open(spec_path) as f:
                spec = json.load(f)
            all_issues.extend(check_agent_spec(spec, version))

    # Cross-version check
    v1_memo_path = os.path.join(base, "v1", "memo.json")
    v2_memo_path = os.path.join(base, "v2", "memo.json")
    if os.path.exists(v1_memo_path) and os.path.exists(v2_memo_path):
        with open(v1_memo_path) as f:
            v1_memo = json.load(f)
        with open(v2_memo_path) as f:
            v2_memo = json.load(f)
        all_issues.extend(check_v2_improvement(v1_memo, v2_memo))

    # Changelog check
    all_issues.extend(check_changelog(account_id))

    # Diff report check
    diff_path = os.path.join(base, "diff_report.html")
    if not os.path.exists(diff_path):
        all_issues.append(("WARN", "diff_report.html not found — run diff_viewer.py"))

    errors = [i for i in all_issues if i[0] == "ERROR"]
    warnings = [i for i in all_issues if i[0] == "WARN"]

    return {
        "account_id": account_id,
        "company": ACCOUNT_MAP.get(account_id, {}).get("company", "Unknown"),
        "errors": errors,
        "warnings": warnings,
        "passed": len(errors) == 0,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def print_result(result: dict, verbose: bool):
    C = Colors
    account_id = result["account_id"]
    company = result["company"]
    errors = result["errors"]
    warnings = result["warnings"]
    passed = result["passed"]

    status = f"{C.GREEN}PASS{C.RESET}" if passed else f"{C.RED}FAIL{C.RESET}"
    warn_str = f"  {C.YELLOW}{len(warnings)} warn(s){C.RESET}" if warnings else ""
    err_str = f"  {C.RED}{len(errors)} error(s){C.RESET}" if errors else ""
    print(f"  {status}  {C.BOLD}{account_id}{C.RESET} ({company}){err_str}{warn_str}")

    if verbose or not passed:
        for sev, msg in errors:
            print(f"         {C.RED}✗ [ERROR]{C.RESET} {msg}")
        for sev, msg in warnings:
            print(f"         {C.YELLOW}⚠ [WARN]{C.RESET}  {msg}")


def main():
    parser = argparse.ArgumentParser(description="Validate Clara pipeline outputs.")
    parser.add_argument("--account", default=None, help="Single account to validate (e.g. acc_001)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all warnings and details")
    args = parser.parse_args()

    accounts = [args.account] if args.account else sorted(ACCOUNT_MAP.keys())

    C = Colors
    print(f"\n{C.BOLD}{'='*60}{C.RESET}")
    print(f"{C.BOLD}  Clara Pipeline — Output Validation{C.RESET}")
    print(f"{C.BOLD}{'='*60}{C.RESET}\n")

    results = [validate_account(acc, args.verbose) for acc in accounts]

    for r in results:
        print_result(r, args.verbose)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    total_errors = sum(len(r["errors"]) for r in results)
    total_warnings = sum(len(r["warnings"]) for r in results)

    print(f"\n{C.BOLD}{'='*60}{C.RESET}")
    print(f"  Accounts validated : {total}")
    print(f"  Passed             : {C.GREEN}{passed}{C.RESET}")
    print(f"  Failed             : {C.RED}{total - passed}{C.RESET}")
    print(f"  Total errors       : {C.RED}{total_errors}{C.RESET}")
    print(f"  Total warnings     : {C.YELLOW}{total_warnings}{C.RESET}")
    print(f"{C.BOLD}{'='*60}{C.RESET}\n")

    sys.exit(0 if total_errors == 0 else 1)


if __name__ == "__main__":
    main()
