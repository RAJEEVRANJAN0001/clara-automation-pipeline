#!/usr/bin/env python3
"""
dashboard.py — Generate a master HTML dashboard for all processed accounts.

Produces outputs/reports/dashboard.html with:
  - Summary cards for all 5 accounts
  - v1 vs v2 comparison tables
  - Changelog highlights
  - Agent spec previews
  - Pipeline status at a glance

Usage:
    python scripts/dashboard.py
    python scripts/dashboard.py --open   # Auto-open in browser
"""

import argparse
import json
import os
import sys
import webbrowser
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from config import ACCOUNTS_DIR, CHANGELOG_DIR, REPORTS_DIR, ACCOUNT_MAP


def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def load_text(path):
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return ""


def changelog_lines(account_id):
    text = load_text(os.path.join(CHANGELOG_DIR, f"{account_id}_changes.md"))
    lines = [l.strip() for l in text.splitlines() if l.strip().startswith("-")]
    return lines


def pipeline_status(account_id):
    base = os.path.join(ACCOUNTS_DIR, account_id)
    status = {}
    for ver in ["v1", "v2"]:
        v_dir = os.path.join(base, ver)
        status[ver] = {
            "memo": os.path.exists(os.path.join(v_dir, "memo.json")),
            "agent": os.path.exists(os.path.join(v_dir, "agent_spec.json")),
        }
    status["diff"] = os.path.exists(os.path.join(base, "diff_report.html"))
    status["changelog"] = os.path.exists(os.path.join(CHANGELOG_DIR, f"{account_id}_changes.md"))
    return status


def tick(ok):
    return "<span class='tick'>✓</span>" if ok else "<span class='cross'>✗</span>"


def generate_dashboard():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    account_cards = []
    status_rows = []
    total_changes = 0

    for acc_id, acc_info in ACCOUNT_MAP.items():
        base = os.path.join(ACCOUNTS_DIR, acc_id)
        v1_memo = load_json(os.path.join(base, "v1", "memo.json"))
        v2_memo = load_json(os.path.join(base, "v2", "memo.json"))
        v1_spec = load_json(os.path.join(base, "v1", "agent_spec.json"))
        v2_spec = load_json(os.path.join(base, "v2", "agent_spec.json"))
        changes = changelog_lines(acc_id)
        st = pipeline_status(acc_id)
        total_changes += len(changes)

        # Build hours string
        hrs = v2_memo.get("business_hours", {})
        hours_str = f"{hrs.get('days','N/A')} {hrs.get('start','')}–{hrs.get('end','')} {hrs.get('timezone','')}"
        if hrs.get("saturday"):
            sat = hrs["saturday"]
            hours_str += f" | Sat {sat.get('start','')}–{sat.get('end','')}"

        services = v2_memo.get("services_supported", [])
        services_html = "".join(f"<span class='badge'>{s}</span>" for s in services[:6])
        if len(services) > 6:
            services_html += f"<span class='badge more'>+{len(services)-6} more</span>"

        emergency_keywords = v2_memo.get("emergency_definition", [])
        em_html = ", ".join(emergency_keywords[:4]) or "N/A"

        er = v2_memo.get("emergency_routing_rules", {})
        primary_phone = er.get("primary_phone", "N/A")
        callback_mins = er.get("callback_guarantee_minutes", "N/A")

        changes_html = "".join(f"<li>{c[2:]}</li>" for c in changes[:6])
        if len(changes) > 6:
            changes_html += f"<li class='more-changes'>+ {len(changes)-6} more changes…</li>"

        industry = acc_info.get("industry", "")
        industry_icon = {
            "Plumbing": "🔧", "HVAC": "❄️", "Landscaping": "🌿",
            "Electrical": "⚡", "Pest Control": "🐛"
        }.get(industry, "🏢")

        all_ok = all([st["v1"]["memo"], st["v1"]["agent"], st["v2"]["memo"], st["v2"]["agent"]])
        status_badge = "<span class='status-ok'>Complete</span>" if all_ok else "<span class='status-warn'>Incomplete</span>"

        diff_link = f"../accounts/{acc_id}/diff_report.html"

        account_cards.append(f"""
<div class="card">
  <div class="card-header">
    <span class="industry-icon">{industry_icon}</span>
    <div>
      <h2>{acc_info['company']}</h2>
      <span class="account-id">{acc_id}</span> &nbsp; <span class="industry-tag">{industry}</span>
    </div>
    <div class="card-status">{status_badge}</div>
  </div>

  <div class="card-grid">
    <div class="info-block">
      <h4>Business Hours</h4>
      <p>{hours_str if hours_str.strip('-') else 'Not extracted'}</p>
    </div>
    <div class="info-block">
      <h4>Emergency Triggers</h4>
      <p>{em_html}</p>
    </div>
    <div class="info-block">
      <h4>On-Call Phone</h4>
      <p>{primary_phone}</p>
    </div>
    <div class="info-block">
      <h4>Callback Guarantee</h4>
      <p>{callback_mins} min</p>
    </div>
  </div>

  <div class="info-block services-block">
    <h4>Services Supported (v2)</h4>
    <div>{services_html}</div>
  </div>

  <div class="changes-block">
    <h4>Onboarding Changes <span class="change-count">{len(changes)}</span></h4>
    <ul class="changes-list">{changes_html}</ul>
  </div>

  <div class="card-footer">
    <a href="{diff_link}" class="btn-diff" target="_blank">📊 View Diff Report</a>
    <span class="pipeline-icons">
      v1 memo {tick(st['v1']['memo'])}
      v1 agent {tick(st['v1']['agent'])}
      v2 memo {tick(st['v2']['memo'])}
      v2 agent {tick(st['v2']['agent'])}
      diff {tick(st['diff'])}
      changelog {tick(st['changelog'])}
    </span>
  </div>
</div>""")

        status_rows.append(f"""
<tr>
  <td><strong>{acc_id}</strong></td>
  <td>{acc_info['company']}</td>
  <td>{industry_icon} {industry}</td>
  <td>{tick(st['v1']['memo'])} {tick(st['v1']['agent'])}</td>
  <td>{tick(st['v2']['memo'])} {tick(st['v2']['agent'])}</td>
  <td>{tick(st['diff'])}</td>
  <td>{tick(st['changelog'])}</td>
  <td><strong>{len(changes)}</strong></td>
</tr>""")

    cards_html = "\n".join(account_cards)
    table_rows_html = "\n".join(status_rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Clara Retell Automation — Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #f4f6f9; color: #1a1a2e; line-height: 1.5; }}

  /* Header */
  .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
             color: white; padding: 32px 40px; }}
  .header h1 {{ font-size: 1.8rem; font-weight: 700; }}
  .header p {{ opacity: 0.85; margin-top: 6px; }}
  .header-meta {{ display: flex; gap: 24px; margin-top: 16px; }}
  .meta-stat {{ background: rgba(255,255,255,0.15); border-radius: 8px;
                padding: 10px 18px; text-align: center; }}
  .meta-stat .num {{ font-size: 1.6rem; font-weight: 700; }}
  .meta-stat .lbl {{ font-size: 0.75rem; opacity: 0.85; }}

  /* Main */
  .main {{ max-width: 1280px; margin: 0 auto; padding: 32px 20px; }}
  section {{ margin-bottom: 48px; }}
  h3.section-title {{ font-size: 1.1rem; text-transform: uppercase; letter-spacing: 0.08em;
                       color: #667eea; margin-bottom: 20px; border-bottom: 2px solid #e2e6f0; padding-bottom: 8px; }}

  /* Cards */
  .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(560px, 1fr)); gap: 24px; }}
  .card {{ background: white; border-radius: 16px; box-shadow: 0 2px 12px rgba(0,0,0,.07);
           overflow: hidden; transition: box-shadow .2s; }}
  .card:hover {{ box-shadow: 0 6px 24px rgba(0,0,0,.12); }}
  .card-header {{ display: flex; align-items: flex-start; gap: 14px; padding: 22px 24px 16px;
                  border-bottom: 1px solid #f0f2f7; }}
  .card-header h2 {{ font-size: 1.1rem; font-weight: 700; }}
  .industry-icon {{ font-size: 2rem; line-height: 1; }}
  .account-id {{ font-size: 0.75rem; background: #eef2ff; color: #667eea; padding: 2px 8px;
                 border-radius: 20px; font-weight: 600; }}
  .industry-tag {{ font-size: 0.75rem; background: #f0fdf4; color: #16a34a; padding: 2px 8px;
                   border-radius: 20px; font-weight: 600; }}
  .card-status {{ margin-left: auto; }}
  .status-ok {{ background: #dcfce7; color: #166534; font-size: 0.75rem; padding: 4px 10px;
                border-radius: 20px; font-weight: 600; }}
  .status-warn {{ background: #fef3c7; color: #92400e; font-size: 0.75rem; padding: 4px 10px;
                  border-radius: 20px; font-weight: 600; }}

  .card-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: #f0f2f7; }}
  .info-block {{ padding: 14px 24px; background: white; }}
  .info-block h4 {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: .06em;
                    color: #9ca3af; margin-bottom: 4px; }}
  .info-block p {{ font-size: 0.88rem; color: #374151; }}

  .services-block {{ padding: 14px 24px; border-top: 1px solid #f0f2f7; }}
  .badge {{ display: inline-block; background: #f3f4f6; color: #374151; font-size: 0.75rem;
            padding: 3px 10px; border-radius: 20px; margin: 3px 3px 3px 0; }}
  .badge.more {{ background: #e0e7ff; color: #4338ca; }}

  .changes-block {{ padding: 16px 24px; border-top: 1px solid #f0f2f7; }}
  .changes-block h4 {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: .06em;
                       color: #9ca3af; margin-bottom: 8px; }}
  .change-count {{ background: #fef3c7; color: #92400e; font-size: 0.7rem; padding: 1px 7px;
                   border-radius: 20px; font-weight: 600; margin-left: 6px; }}
  .changes-list {{ list-style: none; padding: 0; }}
  .changes-list li {{ font-size: 0.82rem; color: #4b5563; padding: 3px 0 3px 14px;
                      position: relative; border-bottom: 1px solid #f9fafb; }}
  .changes-list li::before {{ content: "→"; position: absolute; left: 0; color: #667eea; }}
  .more-changes {{ color: #9ca3af !important; font-style: italic; }}

  .card-footer {{ display: flex; align-items: center; justify-content: space-between;
                  padding: 14px 24px; background: #f9fafb; border-top: 1px solid #f0f2f7; }}
  .btn-diff {{ background: #667eea; color: white; text-decoration: none; font-size: 0.8rem;
               padding: 7px 16px; border-radius: 8px; font-weight: 600; transition: background .2s; }}
  .btn-diff:hover {{ background: #4f46e5; }}
  .pipeline-icons {{ font-size: 0.75rem; color: #6b7280; }}
  .tick {{ color: #16a34a; font-weight: 700; }}
  .cross {{ color: #dc2626; font-weight: 700; }}

  /* Status Table */
  table {{ width: 100%; border-collapse: collapse; background: white;
           border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
  th {{ background: #f8fafc; font-size: 0.78rem; text-transform: uppercase;
        letter-spacing: .05em; color: #6b7280; padding: 12px 16px; text-align: left;
        border-bottom: 2px solid #e5e7eb; }}
  td {{ padding: 12px 16px; font-size: 0.88rem; border-bottom: 1px solid #f3f4f6; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f9fafb; }}

  /* Footer */
  .footer {{ text-align: center; padding: 24px; color: #9ca3af; font-size: 0.8rem; }}
</style>
</head>
<body>

<div class="header">
  <h1>🤖 Clara Retell Automation — Pipeline Dashboard</h1>
  <p>Zero-cost automation: Demo Call → Retell Agent Draft → Onboarding Updates → Agent Revision</p>
  <div class="header-meta">
    <div class="meta-stat">
      <div class="num">{len(ACCOUNT_MAP)}</div>
      <div class="lbl">Accounts</div>
    </div>
    <div class="meta-stat">
      <div class="num">10</div>
      <div class="lbl">Transcripts</div>
    </div>
    <div class="meta-stat">
      <div class="num">{total_changes}</div>
      <div class="lbl">Total Changes</div>
    </div>
    <div class="meta-stat">
      <div class="num">{len(ACCOUNT_MAP) * 2}</div>
      <div class="lbl">Agent Versions</div>
    </div>
    <div class="meta-stat">
      <div class="num">$0</div>
      <div class="lbl">API Cost</div>
    </div>
  </div>
</div>

<div class="main">

  <section>
    <h3 class="section-title">Pipeline Status</h3>
    <table>
      <thead>
        <tr>
          <th>Account</th><th>Company</th><th>Industry</th>
          <th>v1 Outputs</th><th>v2 Outputs</th>
          <th>Diff Report</th><th>Changelog</th><th>Changes</th>
        </tr>
      </thead>
      <tbody>
        {table_rows_html}
      </tbody>
    </table>
  </section>

  <section>
    <h3 class="section-title">Account Details</h3>
    <div class="cards-grid">
      {cards_html}
    </div>
  </section>

</div>

<div class="footer">
  Generated by Clara Retell Automation Pipeline v2.0.0 &nbsp;·&nbsp; {now}
</div>

</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate HTML dashboard for pipeline outputs.")
    parser.add_argument("--open", action="store_true", help="Open dashboard in browser after generating")
    args = parser.parse_args()

    os.makedirs(REPORTS_DIR, exist_ok=True)
    output_path = os.path.join(REPORTS_DIR, "dashboard.html")

    html = generate_dashboard()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✓ Dashboard generated: {output_path}")

    if args.open:
        webbrowser.open(f"file://{output_path}")
        print("  Opened in browser.")


if __name__ == "__main__":
    main()
