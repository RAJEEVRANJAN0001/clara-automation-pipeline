#!/usr/bin/env python3
"""
task_tracker.py — Zero-cost task tracker for the Clara Automation Pipeline.

Creates and manages a local JSON task log (free alternative to Asana).
One task item is created per account per pipeline run, stored in:
  outputs/task_tracker.json

Usage:
    python scripts/task_tracker.py --list
    python scripts/task_tracker.py --account acc_001
    python scripts/task_tracker.py --create-all
    python scripts/task_tracker.py --complete acc_001
    python scripts/task_tracker.py --export-html
"""

import argparse
import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from config import ACCOUNT_MAP, Colors, OUTPUTS_DIR, ACCOUNTS_DIR

TRACKER_FILE = os.path.join(OUTPUTS_DIR, "task_tracker.json")
TRACKER_HTML = os.path.join(OUTPUTS_DIR, "reports", "tasks.html")


# ──────────────────────────────────────────────────────────────────────────────
# Core helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load() -> list:
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def _save(tasks: list) -> None:
    os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)


def _task_id(account_id: str, pipeline: str) -> str:
    return f"TASK-{account_id.upper()}-{pipeline.upper()}"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ──────────────────────────────────────────────────────────────────────────────
# Task operations
# ──────────────────────────────────────────────────────────────────────────────

def create_task(account_id: str, pipeline: str, description: str = "") -> dict:
    """Create a task item for an account pipeline step."""
    info = ACCOUNT_MAP.get(account_id, {})
    task = {
        "task_id": _task_id(account_id, pipeline),
        "account_id": account_id,
        "company": info.get("company", account_id),
        "pipeline": pipeline,  # "A" or "B"
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
        "completed_at": None,
        "description": description or f"Pipeline {pipeline}: {'Demo → v1 agent spec' if pipeline == 'A' else 'Onboarding → v2 agent spec + changelog'}",
        "outputs": {
            "memo": f"outputs/accounts/{account_id}/{'v1' if pipeline == 'A' else 'v2'}/memo.json",
            "agent_spec": f"outputs/accounts/{account_id}/{'v1' if pipeline == 'A' else 'v2'}/agent_spec.json",
            "changelog": f"changelog/{account_id}_changes.md" if pipeline == "B" else None,
            "diff_report": f"outputs/accounts/{account_id}/diff_report.html" if pipeline == "B" else None,
        },
        "notes": [],
    }
    return task


def upsert_task(tasks: list, task: dict) -> list:
    """Insert or update a task by task_id."""
    for i, t in enumerate(tasks):
        if t["task_id"] == task["task_id"]:
            tasks[i] = task
            return tasks
    tasks.append(task)
    return tasks


def mark_complete(tasks: list, account_id: str, pipeline: str = None) -> list:
    """Mark one or all pipeline tasks for an account as complete."""
    now = _now()
    for t in tasks:
        if t["account_id"] == account_id:
            if pipeline is None or t["pipeline"] == pipeline:
                t["status"] = "complete"
                t["completed_at"] = now
                t["updated_at"] = now
    return tasks


def mark_in_progress(tasks: list, account_id: str, pipeline: str) -> list:
    """Mark a task as in-progress."""
    tid = _task_id(account_id, pipeline)
    for t in tasks:
        if t["task_id"] == tid:
            t["status"] = "in_progress"
            t["updated_at"] = _now()
    return tasks


def auto_sync(tasks: list) -> list:
    """Auto-detect which tasks are complete based on existing output files."""
    project_root = os.path.dirname(SCRIPT_DIR)
    for t in tasks:
        acc = t["account_id"]
        pipeline = t["pipeline"]
        version = "v1" if pipeline == "A" else "v2"
        memo_path = os.path.join(project_root, "outputs", "accounts", acc, version, "memo.json")
        spec_path = os.path.join(project_root, "outputs", "accounts", acc, version, "agent_spec.json")
        if os.path.exists(memo_path) and os.path.exists(spec_path):
            if t["status"] == "pending":
                t["status"] = "complete"
                t["completed_at"] = _now()
                t["updated_at"] = _now()
                t["notes"].append("Auto-verified: output files found")
    return tasks


# ──────────────────────────────────────────────────────────────────────────────
# Create all tasks
# ──────────────────────────────────────────────────────────────────────────────

def create_all_tasks() -> list:
    """Create task items for all accounts × both pipelines."""
    tasks = _load()
    for account_id in ACCOUNT_MAP:
        for pipeline in ("A", "B"):
            task = create_task(account_id, pipeline)
            tasks = upsert_task(tasks, task)
    tasks = auto_sync(tasks)
    _save(tasks)
    return tasks


# ──────────────────────────────────────────────────────────────────────────────
# Display
# ──────────────────────────────────────────────────────────────────────────────

STATUS_COLOR = {
    "complete": Colors.GREEN,
    "in_progress": Colors.YELLOW,
    "pending": Colors.RED,
}

STATUS_ICON = {
    "complete": "[DONE]",
    "in_progress": "[WIP ]",
    "pending": "[TODO]",
}


def print_tasks(tasks: list, account_id: str = None) -> None:
    filtered = [t for t in tasks if account_id is None or t["account_id"] == account_id]
    if not filtered:
        print("No tasks found.")
        return

    print()
    print(Colors.BOLD + f"  Clara Task Tracker  ({len(filtered)} tasks)" + Colors.RESET)
    print("  " + "─" * 58)

    for t in filtered:
        c = STATUS_COLOR.get(t["status"], "")
        icon = STATUS_ICON.get(t["status"], "")
        print(f"  {c}{icon}{Colors.RESET}  {Colors.BOLD}{t['task_id']}{Colors.RESET}")
        print(f"         Company:  {t['company']}")
        print(f"         Pipeline: {t['pipeline']}  ({t['description']})")
        print(f"         Status:   {c}{t['status']}{Colors.RESET}")
        if t.get("completed_at"):
            print(f"         Done at:  {t['completed_at']}")
        print()

    total = len(filtered)
    done = sum(1 for t in filtered if t["status"] == "complete")
    pct = int(done / total * 100) if total else 0
    c = Colors.GREEN if done == total else Colors.YELLOW
    print(f"  {c}{done}/{total} complete ({pct}%){Colors.RESET}")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# HTML export
# ──────────────────────────────────────────────────────────────────────────────

def export_html(tasks: list) -> str:
    status_badge = {
        "complete": "<span style='background:#22c55e;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px'>DONE</span>",
        "in_progress": "<span style='background:#f59e0b;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px'>WIP</span>",
        "pending": "<span style='background:#ef4444;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px'>TODO</span>",
    }

    rows = ""
    for t in tasks:
        badge = status_badge.get(t["status"], t["status"])
        outputs = t["outputs"]
        memo_path = outputs.get("memo")
        spec_path = outputs.get("agent_spec")
        cl_path = outputs.get("changelog")
        memo_link = f"<a href='../{memo_path}'>memo.json</a>" if memo_path else "\u2014"
        spec_link = f"<a href='../{spec_path}'>agent_spec.json</a>" if spec_path else "\u2014"
        cl_link = f"<a href='../../../{cl_path}'>changelog</a>" if cl_path else "\u2014"
        done = t.get("completed_at") or "\u2014"
        tid = t['task_id']
        company = t['company']
        pipeline = t['pipeline']
        rows += f"""
        <tr>
          <td style='font-weight:600'>{tid}</td>
          <td>{company}</td>
          <td>Pipeline {pipeline}</td>
          <td>{badge}</td>
          <td>{memo_link} &nbsp; {spec_link} &nbsp; {cl_link}</td>
          <td style='font-size:12px;color:#888'>{done}</td>
        </tr>"""

    total = len(tasks)
    done_count = sum(1 for t in tasks if t["status"] == "complete")
    pct = int(done_count / total * 100) if total else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Clara Task Tracker</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: #f8fafc; color: #1e293b; }}
  header {{ background: linear-gradient(135deg, #7c3aed, #4f46e5); color: white; padding: 32px 40px; }}
  header h1 {{ margin: 0 0 8px; font-size: 26px; }}
  header p {{ margin: 0; opacity: .8; }}
  .stats {{ display: flex; gap: 24px; padding: 24px 40px; background: white; border-bottom: 1px solid #e2e8f0; }}
  .stat {{ text-align: center; }}
  .stat .val {{ font-size: 28px; font-weight: 700; color: #7c3aed; }}
  .stat .lbl {{ font-size: 13px; color: #64748b; margin-top: 2px; }}
  .progress {{ height: 8px; background: #e2e8f0; border-radius: 4px; margin: 0 40px 0; }}
  .progress-bar {{ height: 8px; background: #22c55e; border-radius: 4px; width: {pct}%; transition: width .5s; }}
  .container {{ padding: 24px 40px; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  th {{ background: #f1f5f9; padding: 12px 16px; text-align: left; font-size: 13px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }}
  td {{ padding: 12px 16px; border-top: 1px solid #f1f5f9; font-size: 14px; }}
  tr:hover td {{ background: #fafafa; }}
  a {{ color: #7c3aed; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .footer {{ text-align: center; color: #94a3b8; font-size: 13px; padding: 32px; }}
</style>
</head>
<body>
<header>
  <h1>Clara Task Tracker</h1>
  <p>Automation Pipeline — Account Processing Tasks</p>
</header>
<div class="stats">
  <div class="stat"><div class="val">{total}</div><div class="lbl">Total Tasks</div></div>
  <div class="stat"><div class="val">{done_count}</div><div class="lbl">Complete</div></div>
  <div class="stat"><div class="val">{total - done_count}</div><div class="lbl">Remaining</div></div>
  <div class="stat"><div class="val">{pct}%</div><div class="lbl">Progress</div></div>
</div>
<div style="padding: 12px 40px 0; background:white; border-bottom:1px solid #e2e8f0;">
  <div class="progress"><div class="progress-bar"></div></div>
</div>
<div class="container">
  <table>
    <thead>
      <tr>
        <th>Task ID</th><th>Company</th><th>Pipeline</th><th>Status</th><th>Outputs</th><th>Completed At</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<div class="footer">Generated by Clara Automation Pipeline &mdash; {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}</div>
</body>
</html>"""

    os.makedirs(os.path.dirname(TRACKER_HTML), exist_ok=True)
    with open(TRACKER_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    return TRACKER_HTML


# ──────────────────────────────────────────────────────────────────────────────
# Public API (used by run_pipeline.py)
# ──────────────────────────────────────────────────────────────────────────────

def record_pipeline_start(account_id: str, pipeline: str) -> None:
    """Called at start of a pipeline run to mark task in_progress."""
    tasks = _load()
    # Create if not exists
    task = create_task(account_id, pipeline)
    tasks = upsert_task(tasks, task)
    tasks = mark_in_progress(tasks, account_id, pipeline)
    _save(tasks)


def record_pipeline_complete(account_id: str, pipeline: str) -> None:
    """Called on successful pipeline completion to mark task done."""
    tasks = _load()
    task = create_task(account_id, pipeline)
    tasks = upsert_task(tasks, task)
    tasks = mark_complete(tasks, account_id, pipeline)
    _save(tasks)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Clara Task Tracker — zero-cost Asana alternative")
    parser.add_argument("--list", action="store_true", help="List all tasks")
    parser.add_argument("--account", default=None, help="Filter by account ID")
    parser.add_argument("--create-all", action="store_true", help="Create tasks for all accounts and auto-sync")
    parser.add_argument("--complete", default=None, metavar="ACCOUNT_ID", help="Mark all tasks for an account complete")
    parser.add_argument("--export-html", action="store_true", help="Export tasks to HTML")
    parser.add_argument("--open", action="store_true", help="Open HTML in browser after export")
    args = parser.parse_args()

    if args.create_all:
        tasks = create_all_tasks()
        print(f"{Colors.GREEN}✓ Created/synced {len(tasks)} tasks → {TRACKER_FILE}{Colors.RESET}")
        print_tasks(tasks)
        return

    tasks = _load()

    if args.complete:
        tasks = mark_complete(tasks, args.complete)
        _save(tasks)
        print(f"{Colors.GREEN}✓ Marked {args.complete} complete{Colors.RESET}")

    if args.export_html or args.open:
        path = export_html(tasks)
        print(f"{Colors.GREEN}✓ HTML exported → {path}{Colors.RESET}")
        if args.open:
            import subprocess
            subprocess.run(["open", path])
        return

    if args.list or args.account:
        print_tasks(tasks, account_id=args.account)
        return

    # Default: create-all + list
    tasks = create_all_tasks()
    print_tasks(tasks)


if __name__ == "__main__":
    main()
