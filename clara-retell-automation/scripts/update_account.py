#!/usr/bin/env python3
"""
update_account.py — Apply onboarding call updates to an existing account memo.

Reads an onboarding transcript, extracts updates, applies them to the existing
v1 memo, generates a v2 memo and agent spec, and produces a changelog.

Usage:
    python scripts/update_account.py <onboarding_transcript> --account-id <id> \\
        --v1-memo <path/to/v1/memo.json> --output-dir <path/to/v2/>
"""

import argparse
import json
import os
import re
import sys
from copy import deepcopy


def extract_onboarding_updates(transcript: str) -> dict:
    """Extract updates from an onboarding call transcript."""
    updates = {}

    # Extract updated business hours
    hours_update = {}

    # Check for new days
    days_match = re.search(
        r"(?:now|we're|changed to)\s+(Monday\s+through\s+(?:Friday|Saturday|Sunday))",
        transcript,
        re.IGNORECASE,
    )
    if days_match:
        hours_update["days"] = days_match.group(1).strip()

    # Check for new weekday times
    time_matches = re.findall(
        r"(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s+to\s+(\d{1,2}(?::\d{2})?\s*(?:AM|PM))",
        transcript,
        re.IGNORECASE,
    )
    if time_matches:
        hours_update["start"] = normalize_time(time_matches[0][0])
        hours_update["end"] = normalize_time(time_matches[0][1])

    # Saturday hours
    sat_match = re.search(
        r"[Ss]aturday[s]?\s+(?:is\s+(?:new,?\s+)?|from\s+|hours?\s+)?(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s+to\s+(\d{1,2}(?::\d{2})?\s*(?:AM|PM))",
        transcript,
        re.IGNORECASE,
    )
    dropped_saturday = re.search(r"dropped\s+[Ss]aturday", transcript, re.IGNORECASE)

    if sat_match:
        hours_update["saturday"] = {
            "start": normalize_time(sat_match.group(1)),
            "end": normalize_time(sat_match.group(2)),
        }
    elif dropped_saturday:
        hours_update["saturday"] = None

    if hours_update:
        updates["business_hours"] = hours_update

    # New address
    addr_match = re.search(
        r"(?:New address|moved)\s+(?:is\s+)?(\d+\s+.+?(?:Street|Avenue|Drive|Boulevard|Lane|Road|Way|Blvd|Ave|Dr|St|Rd|Ln)\s*,\s*[A-Z][A-Za-z]+(?:\s+[A-Za-z]+)?\s*,\s*[A-Z]{2})",
        transcript,
        re.IGNORECASE,
    )
    if addr_match:
        updates["office_address"] = addr_match.group(1).strip()

    # New services
    new_services = []
    service_patterns = [
        r"(?:added|now (?:also )?(?:do|offer|started))\s+(.+?)(?:\.|Also|And)",
        r"(?:started offering|now also offer)\s+(.+?)(?:\.|Also|And|Those)",
        r"(?:we now (?:also )?do)\s+(.+?)(?:\.|Also|And)",
    ]
    for pattern in service_patterns:
        matches = re.findall(pattern, transcript, re.IGNORECASE)
        for m in matches:
            items = re.split(r"\s+and\s+|,\s*", m.strip())
            for item in items:
                cleaned = item.strip().strip(".").lower()
                cleaned = re.sub(r"^(?:also\s+)?", "", cleaned).strip()
                if len(cleaned) > 3 and len(cleaned) < 80:
                    if not re.match(r"(?:we|our|for|the|that|if|those|it)", cleaned, re.IGNORECASE):
                        new_services.append(cleaned)

    if new_services:
        updates["new_services"] = new_services

    # New emergencies
    new_emergencies = []
    emerg_patterns = [
        r"(?:add|adding)\s+(.+?)\s+(?:to (?:our )?emergenc|as an emergenc|to the (?:emergency )?list)",
        r"(?:should (?:also )?be treated as (?:an )?(?:emergency|urgent))\s*[:\-]?\s*(.+?)(?:\.|$)",
    ]
    for pattern in emerg_patterns:
        matches = re.findall(pattern, transcript, re.IGNORECASE)
        for m in matches:
            cleaned = m.strip().strip(".").lower()
            if len(cleaned) > 3:
                new_emergencies.append(cleaned)

    if new_emergencies:
        updates["new_emergencies"] = new_emergencies

    # Updated phone numbers
    phone_updates = {}
    backup_match = re.search(
        r"(?:backup|new backup)\s+(?:number\s+(?:is\s+)?|is\s+(?:now\s+)?)?(?:now\s+)?\d{3}-(\d{4})",
        transcript,
        re.IGNORECASE,
    )
    if backup_match:
        full_match = re.search(r"(\d{3}-\d{4})", backup_match.group(0))
        if full_match:
            phone_updates["backup_phone"] = full_match.group(1)

    callback_match = re.search(
        r"callback\s+guarantee\s+(?:to|from\s+\d+\s+minutes\s+to)\s+(\d+)\s+minutes",
        transcript,
        re.IGNORECASE,
    )
    if not callback_match:
        callback_match = re.search(
            r"(?:reduce|shorten|change|update).*callback.*?(\d+)\s+minutes",
            transcript,
            re.IGNORECASE,
        )
    if callback_match:
        phone_updates["callback_guarantee_minutes"] = int(callback_match.group(1))

    if phone_updates:
        updates["emergency_routing_updates"] = phone_updates

    # Extension changes
    ext_updates = {}
    ext_patterns = re.findall(
        r"(\w[\w\s]+?)\s+(?:to|at)\s+extension\s+(\d+)\s+instead\s+of",
        transcript,
        re.IGNORECASE,
    )
    for name, ext in ext_patterns:
        ext_updates[name.strip().lower()] = f"ext {ext}"

    new_ext_patterns = re.findall(
        r"(?:new|added|added a new)\s+(\w[\w\s]+?)\s+(?:line\s+)?(?:at\s+)?extension\s+(\d+)",
        transcript,
        re.IGNORECASE,
    )
    for name, ext in new_ext_patterns:
        ext_updates[name.strip().lower()] = f"ext {ext}"

    if ext_updates:
        updates["extension_updates"] = ext_updates

    # Additional constraints
    new_constraints = []
    constraint_patterns = re.findall(
        r"(?:don't want|also don't|never|do not)\s+(?:anyone\s+)?(?:creating?|make|use)\s+(.+?)(?:\.|Those|$)",
        transcript,
        re.IGNORECASE,
    )
    for m in constraint_patterns:
        new_constraints.append(m.strip())

    if new_constraints:
        updates["new_constraints"] = new_constraints

    # Additional notes
    notes = []
    note_patterns = [
        r"(?:One (?:more )?thing|One additional thing|Also)\s*[—–-]?\s*(.+?)(?:\n|Agent:)",
        r"(?:we now offer|mention that|make sure to mention)\s+(.+?)(?:\.|$)",
    ]
    for pattern in note_patterns:
        matches = re.findall(pattern, transcript, re.IGNORECASE)
        for m in matches:
            cleaned = m.strip().strip(".")
            if len(cleaned) > 10:
                notes.append(cleaned)

    if notes:
        updates["additional_notes"] = notes

    return updates


def normalize_time(t: str) -> str:
    """Normalize time string to HH:MM format."""
    t = t.strip().upper()
    match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", t)
    if match:
        hour = int(match.group(1))
        minute = match.group(2) or "00"
        period = match.group(3)
        if period == "PM" and hour != 12:
            hour += 12
        elif period == "AM" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute}"
    return t


def apply_updates(v1_memo: dict, updates: dict) -> tuple:
    """Apply updates to the v1 memo and return (v2_memo, changes_list)."""
    v2_memo = deepcopy(v1_memo)
    changes = []

    # Update business hours
    if "business_hours" in updates:
        hours_updates = updates["business_hours"]
        old_hours = v1_memo.get("business_hours", {})

        if "days" in hours_updates:
            old_val = old_hours.get("days", "")
            v2_memo["business_hours"]["days"] = hours_updates["days"]
            if old_val != hours_updates["days"]:
                changes.append(f"Business days updated from '{old_val}' to '{hours_updates['days']}'")

        if "start" in hours_updates:
            old_val = old_hours.get("start", "")
            v2_memo["business_hours"]["start"] = hours_updates["start"]
            if old_val != hours_updates["start"]:
                changes.append(f"Business hours start updated from {old_val} to {hours_updates['start']}")

        if "end" in hours_updates:
            old_val = old_hours.get("end", "")
            v2_memo["business_hours"]["end"] = hours_updates["end"]
            if old_val != hours_updates["end"]:
                changes.append(f"Business hours end updated from {old_val} to {hours_updates['end']}")

        if "saturday" in hours_updates:
            if hours_updates["saturday"] is None:
                if old_hours.get("saturday"):
                    changes.append("Saturday hours removed")
                v2_memo["business_hours"]["saturday"] = None
            else:
                old_sat = old_hours.get("saturday")
                v2_memo["business_hours"]["saturday"] = hours_updates["saturday"]
                if old_sat:
                    changes.append(
                        f"Saturday hours updated to {hours_updates['saturday']['start']}-{hours_updates['saturday']['end']}"
                    )
                else:
                    changes.append(
                        f"Saturday hours added: {hours_updates['saturday']['start']}-{hours_updates['saturday']['end']}"
                    )

    # Update address
    if "office_address" in updates:
        old_addr = v1_memo.get("office_address", "")
        v2_memo["office_address"] = updates["office_address"]
        changes.append(f"Office address updated from '{old_addr}' to '{updates['office_address']}'")

    # Add new services
    if "new_services" in updates:
        existing = v2_memo.get("services_supported", [])
        for svc in updates["new_services"]:
            svc_lower = svc.lower().strip()
            # Skip fragments that are clearly not service names
            if re.match(r"^(?:a couple|saturday|we|our|those|it|the|some|also|both)\b", svc_lower, re.IGNORECASE):
                continue
            if len(svc_lower) < 4 or "hours" in svc_lower or "am to" in svc_lower:
                continue
            if svc_lower not in [s.lower() for s in existing]:
                existing.append(svc_lower)
                changes.append(f"Added service: {svc}")
        v2_memo["services_supported"] = existing

    # Add new emergency definitions
    if "new_emergencies" in updates:
        existing = v2_memo.get("emergency_definition", [])
        for emrg in updates["new_emergencies"]:
            if emrg.lower() not in [e.lower() for e in existing]:
                existing.append(emrg)
                changes.append(f"Added emergency definition: {emrg}")
        v2_memo["emergency_definition"] = existing

    # Update emergency routing
    if "emergency_routing_updates" in updates:
        routing = v2_memo.get("emergency_routing_rules", {})
        for key, val in updates["emergency_routing_updates"].items():
            old_val = routing.get(key, "")
            routing[key] = val
            changes.append(f"Emergency routing '{key}' updated from '{old_val}' to '{val}'")
        v2_memo["emergency_routing_rules"] = routing

    # Update extensions
    if "extension_updates" in updates:
        routing = v2_memo.get("non_emergency_routing_rules", {})
        extensions = routing.get("extensions", {})
        for name, ext in updates["extension_updates"].items():
            old_ext = extensions.get(name, "none")
            extensions[name] = ext
            changes.append(f"Extension for '{name}' updated from '{old_ext}' to '{ext}'")
        routing["extensions"] = extensions
        v2_memo["non_emergency_routing_rules"] = routing

    # Add constraints
    if "new_constraints" in updates:
        existing = v2_memo.get("integration_constraints", [])
        for c in updates["new_constraints"]:
            existing.append(c)
            changes.append(f"Added constraint: {c}")
        v2_memo["integration_constraints"] = existing

    # Add notes
    if "additional_notes" in updates:
        existing_notes = v2_memo.get("notes", "")
        for note in updates["additional_notes"]:
            if existing_notes:
                existing_notes += f" | {note}"
            else:
                existing_notes = note
            changes.append(f"Added note: {note}")
        v2_memo["notes"] = existing_notes

    # Recalculate extraction confidence for v2
    try:
        from extract_account_info import compute_extraction_confidence, generate_questions_or_unknowns
        v2_memo["extraction_confidence"] = compute_extraction_confidence(v2_memo)
        v2_memo["questions_or_unknowns"] = generate_questions_or_unknowns(v2_memo)
    except ImportError:
        pass

    return v2_memo, changes


def generate_changelog(account_id: str, changes: list) -> str:
    """Generate a markdown changelog."""
    md = f"# Changelog: {account_id}\n\n"
    md += "## Version v1 → v2\n\n"
    md += "### Changes:\n"
    for change in changes:
        md += f"- {change}\n"
    md += "\n---\n"
    md += "*Generated by Clara Automation Pipeline*\n"
    return md


def main():
    parser = argparse.ArgumentParser(
        description="Apply onboarding updates to an existing account memo."
    )
    parser.add_argument("file", help="Path to the onboarding transcript file")
    parser.add_argument("--account-id", required=True, help="Account identifier")
    parser.add_argument("--v1-memo", required=True, help="Path to the v1 memo.json")
    parser.add_argument("--output-dir", required=True, help="Output directory for v2 files")
    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.file):
        print(f"ERROR: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.v1_memo):
        print(f"ERROR: v1 memo not found: {args.v1_memo}", file=sys.stderr)
        sys.exit(1)

    # Read inputs
    with open(args.file, "r", encoding="utf-8") as f:
        transcript = f.read()

    with open(args.v1_memo, "r", encoding="utf-8") as f:
        v1_memo = json.load(f)

    # Extract updates
    updates = extract_onboarding_updates(transcript)
    print(f"Extracted {len(updates)} update categories from onboarding transcript.")

    # Apply updates
    v2_memo, changes = apply_updates(v1_memo, updates)
    print(f"Applied {len(changes)} changes.")

    # Save v2 memo
    os.makedirs(args.output_dir, exist_ok=True)
    v2_memo_path = os.path.join(args.output_dir, "memo.json")
    with open(v2_memo_path, "w", encoding="utf-8") as f:
        json.dump(v2_memo, f, indent=2)
    print(f"v2 memo saved to: {v2_memo_path}")

    # Generate v2 agent spec
    # Import the agent spec generator
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from generate_agent_spec import generate_agent_spec

    agent_spec = generate_agent_spec(v2_memo, "v2")
    agent_spec_path = os.path.join(args.output_dir, "agent_spec.json")
    with open(agent_spec_path, "w", encoding="utf-8") as f:
        json.dump(agent_spec, f, indent=2)
    print(f"v2 agent spec saved to: {agent_spec_path}")

    # Generate changelog
    changelog = generate_changelog(args.account_id, changes)
    changelog_path = os.path.join(
        os.path.dirname(os.path.dirname(args.output_dir)),
        "..",
        "..",
        "changelog",
        f"{args.account_id}_changes.md",
    )
    # Normalize path
    changelog_dir = os.path.normpath(os.path.dirname(changelog_path))
    os.makedirs(changelog_dir, exist_ok=True)
    changelog_path = os.path.normpath(changelog_path)
    with open(changelog_path, "w", encoding="utf-8") as f:
        f.write(changelog)
    print(f"Changelog saved to: {changelog_path}")

    # Print summary
    print("\n=== CHANGELOG SUMMARY ===")
    for change in changes:
        print(f"  • {change}")


if __name__ == "__main__":
    main()
