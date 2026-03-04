#!/usr/bin/env python3
"""
generate_agent_spec.py — Generate a Retell Agent specification from an account memo.

Produces a Retell-compatible conversation flow agent configuration
including system prompt, conversation nodes, and transfer protocols.

Usage:
    python scripts/generate_agent_spec.py <memo.json> [--output <path>] [--version v1]
"""

import argparse
import datetime
import json
import os
import sys
import uuid

# Resolve scripts dir for config import
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
try:
    from config import DEFAULT_VOICE, PIPELINE_VERSION, DEFAULT_LANGUAGE
except ImportError:
    DEFAULT_VOICE = "Retell-Cimo"
    PIPELINE_VERSION = "2.0.0"
    DEFAULT_LANGUAGE = "en-US"


def generate_system_prompt(memo: dict) -> str:
    """Generate the system prompt for the Retell agent."""
    company = memo.get("company_name", "the company")
    hours = memo.get("business_hours", {})
    services = memo.get("services_supported", [])
    emergencies = memo.get("emergency_definition", [])
    emergency_routing = memo.get("emergency_routing_rules", {})
    constraints = memo.get("integration_constraints", [])
    address = memo.get("office_address", "")
    notes = memo.get("notes", "")

    # Build hours string
    hours_str = ""
    if hours.get("days"):
        hours_str = f"{hours['days']}, {hours.get('start', '')} to {hours.get('end', '')}"
        if hours.get("timezone"):
            hours_str += f" {hours['timezone']}"
    if hours.get("saturday"):
        sat = hours["saturday"]
        hours_str += f". Saturday: {sat['start']} to {sat['end']}"

    # Build services string
    services_str = ", ".join(services) if services else "general services"

    # Build emergency string
    emergency_str = ", ".join(emergencies) if emergencies else "urgent situations"

    prompt = f"""You are the phone receptionist for {company}.

Your job is to:
• Greet callers professionally
• Understand the caller's issue
• Collect the caller's name and phone number
• Determine whether the issue is an emergency
• Route the call according to the rules

Company Information:
- Company: {company}
- Address: {address}
- Business Hours: {hours_str}
- Services: {services_str}

Emergency Definitions:
The following situations are considered emergencies: {emergency_str}

During business hours:
- Greet the caller warmly and professionally
- Ask how you can help
- Collect the caller's name and phone number
- Determine the type of service needed
- Transfer the call to the appropriate department
- If transfer fails, reassure the caller and promise a callback

After business hours:
- Greet the caller
- Determine if the issue is an emergency
- If emergency: collect name, phone number, and address immediately
- Attempt to transfer to the on-call technician
- If transfer fails: assure the caller someone will call them back shortly
- If not an emergency: take a message with name, phone, and description
- Let them know someone will reach out the next business day

Important Rules:
- Keep questions minimal and professional
- Only collect information needed for routing and dispatch
- Never mention internal systems, tools, or function calls to the caller
- Always end by asking if the caller needs anything else
- Be empathetic and reassuring, especially during emergencies"""

    # Callback guarantee
    callback_mins = memo.get("emergency_routing_rules", {}).get("callback_guarantee_minutes")
    if callback_mins:
        prompt += f"\n\nCallback Guarantee: When a transfer fails or a non-emergency after-hours call is received, assure the caller that someone will call them back within {callback_mins} minutes."

    if constraints:
        constraint_str = "\n".join(f"- {c}" for c in constraints)
        prompt += f"\n\nIntegration Constraints:\n{constraint_str}"

    if notes:
        prompt += f"\n\nAdditional Notes: {notes}"

    return prompt


def generate_conversation_flow(memo: dict, version: str) -> dict:
    """Generate a Retell conversation flow configuration."""
    company = memo.get("company_name", "the company")
    emergency_routing = memo.get("emergency_routing_rules", {})
    primary_phone = emergency_routing.get("primary_phone", "+10000000000")
    backup_phone = emergency_routing.get("backup_phone", "")

    # Format phone for transfer (add country code if needed)
    if primary_phone and not primary_phone.startswith("+"):
        primary_phone = f"+1{primary_phone.replace('-', '')}"

    flow_id = f"conversation_flow_{uuid.uuid4().hex[:12]}"
    start_node_id = f"start-node-{uuid.uuid4().hex[:10]}"
    extract_node_id = f"node-extract-{uuid.uuid4().hex[:8]}"
    branch_node_id = f"node-branch-{uuid.uuid4().hex[:8]}"
    emergency_conv_id = f"node-emerg-conv-{uuid.uuid4().hex[:8]}"
    transfer_node_id = f"node-transfer-{uuid.uuid4().hex[:8]}"
    fail_conv_id = f"node-fail-conv-{uuid.uuid4().hex[:8]}"
    end_fail_id = f"node-end-fail-{uuid.uuid4().hex[:8]}"
    end_call_id = f"end-call-{uuid.uuid4().hex[:10]}"
    non_emerg_id = f"node-non-emerg-{uuid.uuid4().hex[:8]}"
    end_non_emerg_id = f"node-end-nonemerg-{uuid.uuid4().hex[:8]}"

    emergencies = memo.get("emergency_definition", [])
    emergency_str = ", ".join(emergencies) if emergencies else "urgent situations"

    nodes = [
        {
            "instruction": {
                "type": "prompt",
                "text": f"Hello, thank you for calling {company}. How may I help you today?",
            },
            "name": "Greeting",
            "edges": [
                {
                    "destination_node_id": extract_node_id,
                    "id": f"edge-greet-{uuid.uuid4().hex[:8]}",
                    "transition_condition": {"type": "prompt", "prompt": "Continue"},
                }
            ],
            "start_speaker": "agent",
            "id": start_node_id,
            "type": "conversation",
            "display_position": {"x": -220, "y": -670},
        },
        {
            "variables": [
                {
                    "name": "caller_name",
                    "description": "The name of the person calling.",
                    "type": "string",
                    "choices": [],
                },
                {
                    "name": "caller_phone",
                    "description": "The phone number of the caller so the company can call them back.",
                    "type": "string",
                    "choices": [],
                },
                {
                    "name": "problem_description",
                    "description": "A short description of the problem or reason the caller is contacting the company.",
                    "type": "string",
                    "choices": [],
                },
                {
                    "name": "is_emergency",
                    "description": f"Whether the caller's problem is an emergency such as {emergency_str}.",
                    "type": "boolean",
                    "choices": [],
                },
                {
                    "name": "caller_address",
                    "description": "The address of the caller, collected for emergency dispatch.",
                    "type": "string",
                    "choices": [],
                },
            ],
            "else_edge": {
                "destination_node_id": non_emerg_id,
                "id": f"{extract_node_id}-else-edge",
                "transition_condition": {"type": "prompt", "prompt": "Else"},
            },
            "name": "Extract Variables",
            "edges": [
                {
                    "id": f"edge-extract-{uuid.uuid4().hex[:8]}",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Describe the transition condition",
                    },
                }
            ],
            "id": extract_node_id,
            "type": "extract_dynamic_variables",
            "display_position": {"x": 5, "y": -275},
        },
        {
            "name": "Logic Split",
            "edges": [
                {
                    "destination_node_id": emergency_conv_id,
                    "id": f"edge-branch-{uuid.uuid4().hex[:8]}",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "is_emergency == true",
                    },
                }
            ],
            "id": branch_node_id,
            "else_edge": {
                "destination_node_id": non_emerg_id,
                "id": f"edge-branch-else-{uuid.uuid4().hex[:8]}",
                "transition_condition": {"type": "prompt", "prompt": "Else"},
            },
            "type": "branch",
            "display_position": {"x": 170, "y": -733},
        },
        {
            "name": "Emergency Conversation",
            "edges": [
                {
                    "destination_node_id": transfer_node_id,
                    "id": f"edge-emerg-{uuid.uuid4().hex[:8]}",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Please hold while I connect you to our emergency technician.",
                    },
                }
            ],
            "id": emergency_conv_id,
            "type": "conversation",
            "display_position": {"x": 370, "y": -390},
            "instruction": {
                "type": "prompt",
                "text": "This sounds like an emergency. Let me collect your address and connect you to our technician immediately.",
            },
        },
        {
            "custom_sip_headers": {},
            "transfer_destination": {
                "type": "predefined",
                "number": primary_phone,
            },
            "edge": {
                "destination_node_id": fail_conv_id,
                "id": f"edge-transfer-{uuid.uuid4().hex[:8]}",
                "transition_condition": {
                    "type": "prompt",
                    "prompt": "Transfer failed",
                },
            },
            "name": "Transfer Call",
            "ignore_e164_validation": False,
            "id": transfer_node_id,
            "transfer_option": {
                "type": "cold_transfer",
                "show_transferee_as_caller": False,
                "enable_bridge_audio_cue": True,
            },
            "type": "transfer_call",
            "speak_during_execution": False,
            "display_position": {"x": 580, "y": -677},
        },
        {
            "name": "Transfer Failed",
            "edges": [
                {
                    "destination_node_id": end_fail_id,
                    "id": f"edge-fail-{uuid.uuid4().hex[:8]}",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Thank you for calling. We will get back to you shortly.",
                    },
                }
            ],
            "id": fail_conv_id,
            "type": "conversation",
            "display_position": {"x": 385, "y": -60},
            "instruction": {
                "type": "prompt",
                "text": "I'm sorry, our technician is currently unavailable at the moment. "
                "I will make sure someone calls you back as soon as possible.",
            },
        },
        {
            "name": "End Call (Emergency Fail)",
            "id": end_fail_id,
            "type": "end",
            "speak_during_execution": True,
            "display_position": {"x": 830, "y": -163},
            "instruction": {
                "type": "prompt",
                "text": "Thank you for calling. We will get back to you shortly.",
            },
        },
        {
            "name": "Non-Emergency Handling",
            "edges": [
                {
                    "destination_node_id": end_non_emerg_id,
                    "id": f"edge-nonemerg-{uuid.uuid4().hex[:8]}",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caller has been helped or message taken.",
                    },
                }
            ],
            "id": non_emerg_id,
            "type": "conversation",
            "display_position": {"x": -50, "y": 100},
            "instruction": {
                "type": "prompt",
                "text": "Thank you for letting me know. Let me collect your information so we can assist you. "
                "May I have your name and phone number?",
            },
        },
        {
            "name": "End Call",
            "id": end_non_emerg_id,
            "type": "end",
            "display_position": {"x": 300, "y": 300},
            "instruction": {
                "type": "prompt",
                "text": "Thank you for calling. Is there anything else I can help you with? "
                "Have a great day!",
            },
        },
    ]

    conversation_flow = {
        "conversation_flow_id": flow_id,
        "version": 0,
        "global_prompt": generate_system_prompt(memo),
        "nodes": nodes,
        "start_node_id": start_node_id,
        "start_speaker": "agent",
        "model_choice": {"type": "cascading", "model": "gpt-4.1"},
        "tool_call_strict_mode": True,
        "knowledge_base_ids": [],
        "kb_config": {"top_k": 3, "filter_score": 0.6},
        "is_published": False,
        "is_transfer_cf": False,
    }

    return conversation_flow


def generate_agent_spec(memo: dict, version: str = "v1") -> dict:
    """Generate the full Retell agent specification."""
    company = memo.get("company_name", "Agent")
    conversation_flow = generate_conversation_flow(memo, version)
    account_id = memo.get("account_id", "unknown")
    confidence = memo.get("extraction_confidence", {})
    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    agent_spec = {
        "agent_id": "",
        "channel": "voice",
        "agent_name": f"{company} Assistant",
        "version": version,
        "metadata": {
            "pipeline_version": PIPELINE_VERSION,
            "generated_at": generated_at,
            "account_id": account_id,
            "extraction_confidence": confidence,
        },
        "response_engine": {
            "type": "conversation-flow",
            "version": 0,
            "conversation_flow_id": conversation_flow["conversation_flow_id"],
        },
        "language": DEFAULT_LANGUAGE,
        "data_storage_setting": "everything",
        "opt_in_signed_url": False,
        "is_published": False,
        "post_call_analysis_model": "gpt-4.1-mini",
        "pii_config": {"mode": "post_call", "categories": []},
        "voice_id": DEFAULT_VOICE,
        "voice_style": "friendly",
        "max_call_duration_ms": 3600000,
        "interruption_sensitivity": 0.9,
        "allow_user_dtmf": True,
        "user_dtmf_options": {},
        "variables": {
            "business_hours": memo.get("business_hours", {}),
            "company_name": company,
            "office_address": memo.get("office_address", ""),
            "emergency_routing": memo.get("emergency_routing_rules", {}),
        },
        "call_transfer_protocol": (
            "Transfer emergency calls to on-call technician immediately. "
            "If transfer fails, collect caller info and guarantee callback."
        ),
        "fallback_protocol": (
            "If transfer fails: apologize, collect name, phone number, and address. "
            "Assure the caller someone will call back within the guaranteed timeframe."
        ),
        "conversationFlow": conversation_flow,
    }

    return agent_spec


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Retell agent specification from an account memo."
    )
    parser.add_argument("memo", help="Path to the account memo JSON file")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output file path for the agent spec",
    )
    parser.add_argument(
        "--version",
        default="v1",
        help="Agent version (default: v1)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.memo):
        print(f"ERROR: File not found: {args.memo}", file=sys.stderr)
        sys.exit(1)

    with open(args.memo, "r", encoding="utf-8") as f:
        memo = json.load(f)

    agent_spec = generate_agent_spec(memo, args.version)
    output_json = json.dumps(agent_spec, indent=2)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Agent spec saved to: {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
