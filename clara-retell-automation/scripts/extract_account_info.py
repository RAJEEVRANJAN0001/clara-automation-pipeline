#!/usr/bin/env python3
"""
extract_account_info.py — Extract structured business information from a transcript.

Uses rule-based extraction with keyword matching and pattern recognition.
Zero-cost: no paid LLM API calls required.

Usage:
    python scripts/extract_account_info.py <transcript_file> --account-id <id> [--output <path>]
"""

import argparse
import json
import os
import re
import sys


def extract_company_name(text: str) -> str:
    """Extract company name from transcript."""
    patterns = [
        # Header line: "DEMO CALL TRANSCRIPT — <Company Name>"
        r"TRANSCRIPT\s*[—–\-]+\s*(.+)",
        # Greeting: "Good afternoon, <Company>, this is <Name>"
        r"(?:Good (?:morning|afternoon|evening)),?\s+([A-Z][\w]+(?:\s+[A-Z][\w]+){1,4}),\s+this is",
        # "Thank you for calling <Company>"
        r"(?:calling|for calling)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,4}?)[\.\,\!]",
        # "<Company> has been"
        r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,4})\s+has been",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip().rstrip(".")
            # Clean up common suffixes
            name = re.sub(r"\s*(this is|my name|how).*$", "", name, flags=re.IGNORECASE)
            if len(name) > 3 and name not in ("Hi", "Hello", "Good", "Thank", "DEMO CALL"):
                return name
    return ""


def extract_business_hours(text: str) -> dict:
    """Extract business hours from transcript."""
    hours_info = {
        "days": "",
        "start": "",
        "end": "",
        "timezone": "",
        "saturday": None,
    }

    # Days pattern
    days_patterns = [
        r"(Monday\s+through\s+(?:Friday|Saturday|Sunday))",
        r"(Mon(?:day)?[\s-]+(?:through|to)[\s-]+(?:Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?))",
    ]
    for pattern in days_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            hours_info["days"] = match.group(1).strip()
            break

    # Time pattern
    time_patterns = [
        r"(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s+to\s+(\d{1,2}(?::\d{2})?\s*(?:AM|PM))",
        r"(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s+(?:through|until)\s+(\d{1,2}(?::\d{2})?\s*(?:AM|PM))",
    ]
    times_found = []
    for pattern in time_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        times_found.extend(matches)

    if times_found:
        hours_info["start"] = normalize_time(times_found[0][0])
        hours_info["end"] = normalize_time(times_found[0][1])

    # Check for Saturday hours separately
    sat_match = re.search(
        r"[Ss]aturday[s]?\s+(?:from\s+|is\s+(?:new,?\s+)?|hours?\s+(?:from\s+)?)?(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\s+to\s+(\d{1,2}(?::\d{2})?\s*(?:AM|PM))",
        text,
        re.IGNORECASE,
    )
    if sat_match:
        hours_info["saturday"] = {
            "start": normalize_time(sat_match.group(1)),
            "end": normalize_time(sat_match.group(2)),
        }

    # Timezone
    tz_match = re.search(r"(Eastern|Central|Mountain|Pacific)\s*(?:Time)?", text, re.IGNORECASE)
    if tz_match:
        tz_map = {
            "eastern": "EST",
            "central": "CST",
            "mountain": "MST",
            "pacific": "PST",
        }
        hours_info["timezone"] = tz_map.get(tz_match.group(1).lower(), tz_match.group(1))

    return hours_info


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


def extract_address(text: str) -> str:
    """Extract office address from transcript."""
    patterns = [
        r"(?:located at|address is|office is at|office at)\s+(.+?)[\.\n]",
        r"(\d+\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*(?:\s+(?:Street|Avenue|Drive|Boulevard|Lane|Road|Way|Blvd|Ave|Dr|St|Rd|Ln))\s*,\s*[A-Z][A-Za-z]+(?:\s+[A-Za-z]+)?\s*,\s*[A-Z]{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".")
    return ""


def _preprocess_service_section(section: str) -> str:
    """Pre-process a service text section before splitting into items."""
    # Collapse em-dash parenthetical examples / qualifiers:
    #   "X — a, b, c — Y" → "X, Y"  (comma-separated single words)
    #   "X — both a and b — Y" → "X, Y"  (both/and pattern)
    section = re.sub(
        r'\s*[—–]\s*(?:both\s+)?\w+(?:\s*(?:,\s*(?:and\s+)?|\s+and\s+)\w+)*\s*[—–]\s*',
        ', ', section,
    )
    # Protect "both X and Y" from being split on "and" (use & placeholder)
    section = re.sub(r'\bboth\s+(\w+)\s+and\s+(\w+)', r'\1 & \2', section)
    # Protect "like X and Y" from being split on "and"
    section = re.sub(r'\blike\s+(\w+(?:\s+\w+)?)\s+and\s+(\w+(?:\s+\w+)?)', r'like \1 & \2', section)
    return section


def _split_service_items(section: str) -> list:
    """Split a pre-processed service section into raw item strings."""
    return re.split(r",\s*(?:and\s+)?|(?:\s+and\s+)|\.\s+", section)


def extract_services(text: str) -> list:
    """Extract services supported from transcript."""
    services = []

    # Strategy: find Agent response blocks that contain service-listing verbs
    agent_blocks = re.findall(r"Agent:\s*(.+?)(?=\nCaller:|\n\n|$)", text, re.DOTALL)

    # Find the block with a service-listing verb and the most commas (= richest list)
    best_block = ""
    best_score = 0
    for block in agent_blocks:
        svc_match = re.search(r"We (?:offer|handle|do|provide)\s+", block, re.IGNORECASE)
        if svc_match:
            # Skip blocks about emergencies ("We do handle emergencies")
            after_verb = block[svc_match.end():svc_match.end()+60].lower()
            if "emergenc" in after_verb:
                continue
            comma_count = block.count(",")
            if comma_count > best_score:
                best_score = comma_count
                best_block = block

    if best_block:
        list_match = re.search(
            r"We (?:offer|handle|do|provide)\s+(.+?)(?:We(?:'re| are| also)|Caller:|\nCaller:|$)",
            best_block, re.IGNORECASE | re.DOTALL,
        )
        if list_match:
            section = _preprocess_service_section(list_match.group(1))
            for item in _split_service_items(section):
                cleaned = _clean_service_item(item)
                if cleaned:
                    services.append(cleaned)

    # Also check for "We also do/offer" sentences in ALL blocks
    for block in agent_blocks:
        for pattern in [r"We also (?:do|offer)\s+(.+?)(?:\.|Caller:|\n\n)"]:
            for m in re.finditer(pattern, block, re.IGNORECASE | re.DOTALL):
                section = _preprocess_service_section(m.group(1))
                for item in _split_service_items(section):
                    cleaned = _clean_service_item(item)
                    if cleaned:
                        services.append(cleaned)

    # --- Post-processing ---
    # 1. Merge lone-word fragments (e.g. "removal") with previous item
    lone_words = {"repair", "removal", "installation", "replacement", "maintenance",
                  "inspection", "residential", "commercial", "treatment", "servicing",
                  "exclusion", "rewiring"}
    merged = []
    for svc in services:
        if svc.strip() in lone_words and merged:
            merged[-1] = f"{merged[-1]} and {svc.strip()}"
        else:
            merged.append(svc)

    # 2. Merge frequency-only fragments with the next item
    #    e.g. "recurring monthly" + "quarterly maintenance plans" → merged
    freq_re = re.compile(
        r'^(?:recurring\s+)?(?:monthly|quarterly|weekly|bi-weekly|annual|yearly|daily)$',
        re.IGNORECASE,
    )
    final = []
    i = 0
    while i < len(merged):
        if i + 1 < len(merged) and freq_re.match(merged[i]):
            final.append(f"{merged[i]} and {merged[i + 1]}")
            i += 2
        else:
            final.append(merged[i])
            i += 1

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for s in final:
        key = s.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def _clean_service_item(item: str) -> str:
    """Clean and validate a single service item. Returns empty string if invalid."""
    cleaned = item.strip().strip(".")
    # Restore & placeholder back to "and"
    cleaned = cleaned.replace(" & ", " and ")
    # Strip leading filler words
    cleaned = re.sub(
        r"^(?:also\s+)?(?:we\s+)?(?:also\s+)?(?:do\s+)?(?:handle\s+)?(?:offer\s+)?",
        "", cleaned, flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(
        r"^(?:in\s+)?(?:both\s+)?(?:a\s+)?(?:the\s+)?(?:wide range of\s+)?",
        "", cleaned, flags=re.IGNORECASE,
    ).strip()
    # Strip trailing "for both <word>" fragments
    cleaned = re.sub(r'\s+for both\s+\w+$', '', cleaned, flags=re.IGNORECASE).strip()
    # Reject too short, too long, sentence-like, or junk
    if len(cleaned) < 4 or len(cleaned) > 80:
        return ""
    if re.match(r"^(?:We|Our|For|If|The|That|I|Those|It|which|who|So|pretty|probably|most)\b", cleaned, re.IGNORECASE):
        return ""
    if "?" in cleaned or cleaned.endswith("years") or cleaned.startswith("fully "):
        return ""
    # Reject known non-service fragments
    reject_words = {"insured", "indoor", "outdoor", "great",
                    "happy to fill you in", "heating",
                    "ventilation", "cooling systems", "both heating", "faucet"}
    if cleaned.lower() in reject_words:
        return ""
    # Reject sentence fragments with person/contact/emergency patterns
    if re.search(r"caller|phone number|address|guarantee|transfer|emergency|urgent|\d{3}-\d{4}", cleaned, re.IGNORECASE):
        return ""
    return cleaned.lower()


def extract_emergency_definitions(text: str) -> list:
    """Extract emergency trigger definitions from transcript."""
    emergencies = []
    section_text = ""

    # Gather ALL matching sections — try multiple patterns
    patterns = [
        # "emergencies include / mean / are / for us" keyword BEFORE the list
        r"(?:emergencies?\s+(?:for us\s+)?(?:include|mean|are|which))[:\s]+(.+?)(?:For emergencies|When you call|Any of these|callers? should|We route|We have)",
        # "and by that we mean X, Y, Z"
        r"(?:and by that we mean|by that we mean)\s+(.+?)(?:we have|callers? should|For emergencies|When|\n\n)",
        # "Emergency situations for us include ..."
        r"[Ee]mergency\s+situations?\s+for us\s+include\s+(.+?)(?:For emergencies|callers? should|\n\n)",
        # "If there's X, Y, Z, those are considered emergencies"
        r"If there(?:'|')s\s+(?:a\s+)?(.+?),\s*(?:those\s+are|that(?:'|')s)\s+considered\s+emergencies",
        # Generic: items before "considered emergencies" / "are emergencies"
        r"([a-z][a-z ,]+?(?:burst|leak|failure|outage|flood|overflow|backup|damage|hazard|infestation|collapse|break|swarm|nest|incursion|wire)[a-z ,]*),?\s+(?:those\s+are|are)\s+considered\s+emergenc",
        # "Emergencies for us include" variant
        r"[Ee]mergencie?s?\s+for\s+us\s+include\s+(.+?)(?:\.|For emergencies|callers|\n)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            section_text = match.group(1)
            break

    if section_text:
        items = re.split(r",\s*(?:and\s+)?|(?:\s+and\s+)|\s*[—–]\s*", section_text)
        for item in items:
            cleaned = item.strip().strip(".")
            cleaned = re.sub(
                r"^(?:things like|such as|like|a\s+|an\s+|any\s+)",
                "", cleaned, flags=re.IGNORECASE,
            ).strip()
            # Remove leading "or"/"and"
            cleaned = re.sub(r"^(?:or|and)\s+", "", cleaned, flags=re.IGNORECASE).strip()
            if 3 <= len(cleaned) <= 80:
                if not re.match(r"^(?:We|Our|For|If|The|That|I|those|they|any of)\b", cleaned, re.IGNORECASE):
                    emergencies.append(cleaned.lower())

    # Deduplicate
    seen = set()
    unique = []
    for e in emergencies:
        if e.lower() not in seen:
            seen.add(e.lower())
            unique.append(e)
    return unique


def extract_emergency_routing(text: str) -> dict:
    """Extract emergency routing rules from transcript."""
    routing = {
        "primary_contact": "",
        "primary_phone": "",
        "backup_phone": "",
        "callback_guarantee_minutes": None,
        "special_instructions": "",
    }

    # Primary contact name — multiple patterns
    contact_patterns = [
        # "our lead tech, Tom" / "our operations manager, Carlos" / "our field supervisor, Derek"
        r"our\s+(?:lead\s+)?(?:tech|technician|electrician|dispatcher|supervisor|manager|crew lead)[,.]?\s+([A-Z][a-z]+)",
        # "on-call technician is <Name>"
        r"(?:on-call|emergency)\s+(?:technician|tech|electrician|dispatcher|supervisor|manager)\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        # "<Name> is our on-call tech"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+is\s+(?:our\s+)?(?:on-call|the\s+emergency)\s+(?:technician|tech)",
        # "route to <Role>, <Name>," pattern
        r"(?:transfer|route)\s+(?:emergency\s+)?(?:calls\s+)?(?:directly\s+)?to\s+our\s+\w+(?:\s+\w+)?,\s+([A-Z][a-z]+),?",
    ]
    for pattern in contact_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().rstrip(",")
            # Reject common false positives (non-name words)
            if name.lower() not in ("the", "our", "reached", "at", "if", "for", "any", "is", "are", "was"):
                # Verify it looks like a proper name (starts uppercase in original text)
                original_span = text[match.start(1):match.end(1)]
                if original_span[0].isupper():
                    routing["primary_contact"] = name
                    break

    # Phone numbers (emergency context)
    phones = re.findall(r"(\d{3}-\d{4})", text)
    if phones:
        routing["primary_phone"] = phones[0]
        if len(phones) > 1:
            routing["backup_phone"] = phones[1]

    # Callback guarantee
    callback_match = re.search(r"(?:guarantee|commit to)\s+(?:a\s+)?callback\s+within\s+(\d+)\s+minutes", text, re.IGNORECASE)
    if not callback_match:
        callback_match = re.search(r"callback\s+within\s+(\d+)\s+minutes", text, re.IGNORECASE)
    if not callback_match:
        callback_match = re.search(r"calls?\s+back\s+within\s+(\d+)\s+minutes", text, re.IGNORECASE)
    if callback_match:
        routing["callback_guarantee_minutes"] = int(callback_match.group(1))

    # Special instructions (e.g., "contact 911")
    danger_match = re.search(r"(?:advise|tell|ask).*(?:contact|call)\s+(911|emergency services)", text, re.IGNORECASE)
    if danger_match:
        routing["special_instructions"] = "Advise caller to contact 911 if immediate danger."

    return routing


def extract_non_emergency_routing(text: str) -> dict:
    """Extract non-emergency routing rules."""
    routing = {
        "during_hours": "Collect name and phone number, determine service type, and transfer or schedule.",
        "after_hours": "Take message with name, phone, and description. Call back next business day.",
    }

    # Extension routing
    extensions = {}
    ext_matches = re.findall(
        r"(?:(?:goes? to|transfer(?:red)? to)\s+)?(\w[\w\s]+?)\s+(?:at\s+)?extension\s+(\d+)",
        text,
        re.IGNORECASE,
    )
    for name, ext in ext_matches:
        extensions[name.strip().lower()] = f"ext {ext}"

    if extensions:
        routing["extensions"] = extensions

    return routing


def extract_call_transfer_rules(text: str) -> dict:
    """Extract call transfer and failure rules."""
    rules = {
        "max_rings_before_fallback": None,
        "transfer_timeout_action": "",
        "transfer_fail_protocol": "",
    }

    # Max rings / timeout before fallback
    rings_match = re.search(r"within\s+(\d+)\s+rings?", text, re.IGNORECASE)
    if rings_match:
        rules["max_rings_before_fallback"] = int(rings_match.group(1))

    # Transfer failure protocol (what happens when transfer fails during business hours)
    fail_patterns = [
        r"[Ii]f (?:a )?transfer fails[,.]?\s*(.+?)(?:\.|Caller:)",
        r"[Ii]f the transfer fails[,.]?\s*(.+?)(?:\.|Caller:)",
        r"transfer fails[,.]?\s*we\s+(.+?)(?:\.|Caller:)",
    ]
    for pattern in fail_patterns:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            rules["transfer_fail_protocol"] = m.group(1).strip().rstrip(".")
            break

    # If we still don't have it, try the broader pattern
    if not rules["transfer_fail_protocol"]:
        fail_match = re.search(
            r"(?:transfer fails|doesn't answer|can't reach)[,.]?\s*(.+?)(?:\.|$)",
            text, re.IGNORECASE,
        )
        if fail_match:
            rules["transfer_fail_protocol"] = fail_match.group(1).strip()

    # Transfer timeout action (callback guarantee for failed transfers during hours)
    timeout_patterns = [
        r"(?:call[ing]* (?:them )?back|reach out|callback)\s+within\s+(?:the\s+)?(\w+\s*(?:hour|minute)s?)",
        r"(?:someone will)\s+(?:call (?:them )?back|reach out)\s+within\s+(?:the\s+)?(\w+\s*(?:hour|minute)s?)",
    ]
    for pattern in timeout_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            rules["transfer_timeout_action"] = f"Callback within {m.group(1).strip()}"
            break

    return rules


def extract_integration_constraints(text: str) -> list:
    """Extract software/integration constraints."""
    constraints = []

    # Look for "never create" / "don't" patterns
    never_patterns = re.findall(
        r"(?:never|don't|do not|should not)\s+(?:create|make|use|accept)\s+(.+?)(?:\.|$)",
        text,
        re.IGNORECASE,
    )
    for match in never_patterns:
        constraints.append(match.strip())

    # Software mentions
    sw_match = re.search(
        r"(?:We use|using)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+for",
        text,
        re.IGNORECASE,
    )
    if sw_match:
        constraints.append(f"Primary system: {sw_match.group(1)}")

    return constraints


def _confidence(value) -> int:
    """Return a 0–100 confidence score for an extracted value."""
    if value is None:
        return 0
    if isinstance(value, bool):
        return 100 if value else 0
    if isinstance(value, list):
        return min(100, len(value) * 20) if value else 0
    if isinstance(value, dict):
        non_empty = sum(1 for v in value.values() if v)
        return min(100, int(non_empty / max(len(value), 1) * 100))
    if isinstance(value, str):
        return 100 if len(value.strip()) > 3 else 0
    if isinstance(value, int):
        return 100 if value > 0 else 0
    return 0


def compute_extraction_confidence(memo: dict) -> dict:
    """Return a per-field confidence dict and an overall avg score."""
    fields = {
        "company_name": memo.get("company_name"),
        "business_hours": memo.get("business_hours"),
        "office_address": memo.get("office_address"),
        "services_supported": memo.get("services_supported"),
        "emergency_definition": memo.get("emergency_definition"),
        "emergency_routing_rules": memo.get("emergency_routing_rules"),
        "callback_guarantee": memo.get("emergency_routing_rules", {}).get("callback_guarantee_minutes"),
        "call_transfer_rules": memo.get("call_transfer_rules"),
        "integration_constraints": memo.get("integration_constraints"),
    }
    scores = {k: _confidence(v) for k, v in fields.items()}
    scores["overall"] = int(sum(scores.values()) / len(scores))
    return scores


def generate_questions_or_unknowns(memo: dict) -> list:
    """Scan memo for empty/missing fields and flag them as questions."""
    questions = []
    confidence = memo.get("extraction_confidence", {})

    # Check critical fields
    if not memo.get("company_name"):
        questions.append("Company name could not be extracted from transcript.")
    if not memo.get("office_address"):
        questions.append("Office address not mentioned in transcript.")
    if not memo.get("services_supported"):
        questions.append("Specific services list not identified — follow up to confirm.")
    if not memo.get("emergency_definition"):
        questions.append("Emergency definitions/triggers not found — confirm what counts as an emergency.")
    er = memo.get("emergency_routing_rules", {})
    if not er.get("primary_contact"):
        questions.append("On-call contact name not identified — confirm emergency contact person.")
    if not er.get("primary_phone"):
        questions.append("Emergency phone number not found in transcript.")
    if er.get("callback_guarantee_minutes") is None:
        questions.append("Callback guarantee time not specified — confirm SLA for emergency callbacks.")
    tr = memo.get("call_transfer_rules", {})
    if not tr.get("transfer_fail_protocol"):
        questions.append("Transfer failure protocol unclear — confirm fallback when call transfer fails.")
    if not memo.get("integration_constraints"):
        questions.append("No software/integration constraints mentioned — confirm primary system.")

    # Also flag low-confidence fields
    for field, score in confidence.items():
        if field == "overall":
            continue
        if 0 < score < 40:
            label = field.replace("_", " ").title()
            questions.append(f"Low confidence extraction for '{label}' — verify with client.")

    return questions


def extract_account_info(transcript: str, account_id: str) -> dict:
    """Extract all structured business information from a transcript."""
    company_name = extract_company_name(transcript)
    business_hours = extract_business_hours(transcript)
    address = extract_address(transcript)
    services = extract_services(transcript)
    emergencies = extract_emergency_definitions(transcript)
    emergency_routing = extract_emergency_routing(transcript)
    non_emergency_routing = extract_non_emergency_routing(transcript)
    transfer_rules = extract_call_transfer_rules(transcript)
    constraints = extract_integration_constraints(transcript)

    # Build the account memo
    memo = {
        "account_id": account_id,
        "company_name": company_name,
        "business_hours": business_hours,
        "office_address": address,
        "services_supported": services,
        "emergency_definition": emergencies,
        "emergency_routing_rules": emergency_routing,
        "non_emergency_routing_rules": non_emergency_routing,
        "call_transfer_rules": transfer_rules,
        "integration_constraints": constraints,
        "after_hours_flow_summary": (
            "After hours: greet caller, determine if emergency. "
            "If emergency: collect name, phone, address, attempt transfer to on-call. "
            "If transfer fails: assure callback. "
            "If non-emergency: take message, callback next business day."
        ),
        "office_hours_flow_summary": (
            "During hours: greet caller, ask how to help, collect name and phone, "
            "determine service type, transfer to appropriate extension/department. "
            "If transfer fails: assure callback within specified timeframe."
        ),
        "questions_or_unknowns": [],
        "notes": f"Auto-extracted from demo call transcript for {company_name}. Confidence scores are per-field estimates; fields below 60% should be verified with the client.",
    }

    # Attach per-field confidence scores (0–100)
    memo["extraction_confidence"] = compute_extraction_confidence(memo)

    # Auto-flag missing or low-confidence fields
    memo["questions_or_unknowns"] = generate_questions_or_unknowns(memo)

    return memo


def main():
    parser = argparse.ArgumentParser(
        description="Extract structured account information from a transcript."
    )
    parser.add_argument("file", help="Path to the transcript file")
    parser.add_argument(
        "--account-id",
        required=True,
        help="Account identifier (e.g., acc_001)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output file path for the JSON memo",
    )
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8") as f:
        transcript = f.read()

    memo = extract_account_info(transcript, args.account_id)

    output_json = json.dumps(memo, indent=2)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Account memo saved to: {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
