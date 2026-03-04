#!/usr/bin/env python3
"""
diff_viewer.py — Generate a visual diff between v1 and v2 account memos.

Outputs an HTML report highlighting all changes between versions.

Usage:
    python scripts/diff_viewer.py --account-id acc_001 [--output-dir outputs]
    python scripts/diff_viewer.py --all  # Generate diffs for all accounts
"""

import argparse
import json
import os
import sys
from datetime import datetime


def json_diff(v1: dict, v2: dict, path: str = "") -> list:
    """Recursively compare two JSON structures and return a list of diffs."""
    diffs = []

    all_keys = set(list(v1.keys()) + list(v2.keys()))
    for key in sorted(all_keys):
        current_path = f"{path}.{key}" if path else key

        if key not in v1:
            diffs.append({"path": current_path, "type": "added", "new": v2[key]})
        elif key not in v2:
            diffs.append({"path": current_path, "type": "removed", "old": v1[key]})
        elif v1[key] != v2[key]:
            if isinstance(v1[key], dict) and isinstance(v2[key], dict):
                diffs.extend(json_diff(v1[key], v2[key], current_path))
            elif isinstance(v1[key], list) and isinstance(v2[key], list):
                added = [i for i in v2[key] if i not in v1[key]]
                removed = [i for i in v1[key] if i not in v2[key]]
                if added or removed:
                    diffs.append({
                        "path": current_path,
                        "type": "modified_list",
                        "added": added,
                        "removed": removed,
                    })
            else:
                diffs.append({
                    "path": current_path,
                    "type": "changed",
                    "old": v1[key],
                    "new": v2[key],
                })

    return diffs


def generate_html_report(account_id: str, diffs: list, v1: dict, v2: dict) -> str:
    """Generate an HTML diff report."""
    company = v2.get("company_name", v1.get("company_name", account_id))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = ""
    for d in diffs:
        if d["type"] == "added":
            rows += f"""
            <tr class="added">
                <td>{d['path']}</td>
                <td><em>(not set)</em></td>
                <td>{json.dumps(d['new'], indent=2) if isinstance(d['new'], (dict, list)) else d['new']}</td>
                <td><span class="badge badge-added">ADDED</span></td>
            </tr>"""
        elif d["type"] == "removed":
            rows += f"""
            <tr class="removed">
                <td>{d['path']}</td>
                <td>{json.dumps(d['old'], indent=2) if isinstance(d['old'], (dict, list)) else d['old']}</td>
                <td><em>(removed)</em></td>
                <td><span class="badge badge-removed">REMOVED</span></td>
            </tr>"""
        elif d["type"] == "changed":
            rows += f"""
            <tr class="changed">
                <td>{d['path']}</td>
                <td>{d['old']}</td>
                <td>{d['new']}</td>
                <td><span class="badge badge-changed">CHANGED</span></td>
            </tr>"""
        elif d["type"] == "modified_list":
            added_str = ", ".join(str(i) for i in d.get("added", []))
            removed_str = ", ".join(str(i) for i in d.get("removed", []))
            old_display = f"Removed: {removed_str}" if removed_str else "(none removed)"
            new_display = f"Added: {added_str}" if added_str else "(none added)"
            rows += f"""
            <tr class="changed">
                <td>{d['path']}</td>
                <td>{old_display}</td>
                <td>{new_display}</td>
                <td><span class="badge badge-changed">MODIFIED</span></td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Diff Report: {account_id} — {company}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; background: #f5f5f5; }}
        h1 {{ color: #1a1a2e; }}
        .meta {{ color: #666; margin-bottom: 2rem; }}
        table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th {{ background: #1a1a2e; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #eee; vertical-align: top; }}
        tr.added td {{ background: #e8f5e9; }}
        tr.removed td {{ background: #ffebee; }}
        tr.changed td {{ background: #fff3e0; }}
        .badge {{ padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
        .badge-added {{ background: #4caf50; color: white; }}
        .badge-removed {{ background: #f44336; color: white; }}
        .badge-changed {{ background: #ff9800; color: white; }}
        .summary {{ background: white; padding: 1rem 1.5rem; border-radius: 8px; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <h1>Version Diff Report: {account_id}</h1>
    <div class="meta">
        <strong>Company:</strong> {company} | <strong>Generated:</strong> {now}
    </div>
    <div class="summary">
        <strong>Summary:</strong> {len(diffs)} change(s) detected between v1 and v2.
    </div>
    <table>
        <thead>
            <tr>
                <th>Field Path</th>
                <th>v1 (Demo)</th>
                <th>v2 (Onboarding)</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate diff reports between v1 and v2 memos.")
    parser.add_argument("--account-id", help="Account to generate diff for")
    parser.add_argument("--all", action="store_true", help="Generate diffs for all accounts")
    parser.add_argument("--output-dir", default="outputs", help="Outputs base directory")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_base = os.path.join(project_root, args.output_dir)

    accounts = []
    if args.all:
        accounts_dir = os.path.join(output_base, "accounts")
        if os.path.exists(accounts_dir):
            accounts = [d for d in os.listdir(accounts_dir) if d.startswith("acc_")]
    elif args.account_id:
        accounts = [args.account_id]
    else:
        print("Specify --account-id or --all")
        sys.exit(1)

    for acc_id in sorted(accounts):
        v1_path = os.path.join(output_base, "accounts", acc_id, "v1", "memo.json")
        v2_path = os.path.join(output_base, "accounts", acc_id, "v2", "memo.json")

        if not os.path.exists(v1_path) or not os.path.exists(v2_path):
            print(f"Skipping {acc_id}: missing v1 or v2 memo")
            continue

        with open(v1_path) as f:
            v1 = json.load(f)
        with open(v2_path) as f:
            v2 = json.load(f)

        diffs = json_diff(v1, v2)
        html = generate_html_report(acc_id, diffs, v1, v2)

        report_path = os.path.join(output_base, "accounts", acc_id, "diff_report.html")
        with open(report_path, "w") as f:
            f.write(html)
        print(f"Diff report generated: {report_path} ({len(diffs)} changes)")


if __name__ == "__main__":
    main()
