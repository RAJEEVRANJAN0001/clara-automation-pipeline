#!/usr/bin/env python3
"""
config.py — Centralized configuration for the Clara Automation Pipeline.

All constants, account mappings, and settings live here.
Import this module in any script to share configuration.
"""

import os

# ─── Project Root ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# ─── Directory Paths ───────────────────────────────────────────────────────────
DATASET_DIR = os.path.join(PROJECT_ROOT, "dataset")
DEMO_CALLS_DIR = os.path.join(DATASET_DIR, "demo_calls")
ONBOARDING_CALLS_DIR = os.path.join(DATASET_DIR, "onboarding_calls")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")
ACCOUNTS_DIR = os.path.join(OUTPUTS_DIR, "accounts")
CHANGELOG_DIR = os.path.join(PROJECT_ROOT, "changelog")
REPORTS_DIR = os.path.join(OUTPUTS_DIR, "reports")

# ─── Account Map ───────────────────────────────────────────────────────────────
ACCOUNT_MAP = {
    "acc_001": {
        "company": "ABC Plumbing",
        "industry": "Plumbing",
        "demo_file": "demo_call_1.txt",
        "onboarding_file": "onboard_call_1.txt",
        "timezone": "EST",
    },
    "acc_002": {
        "company": "Sunshine HVAC Services",
        "industry": "HVAC",
        "demo_file": "demo_call_2.txt",
        "onboarding_file": "onboard_call_2.txt",
        "timezone": "CST",
    },
    "acc_003": {
        "company": "GreenLeaf Landscaping",
        "industry": "Landscaping",
        "demo_file": "demo_call_3.txt",
        "onboarding_file": "onboard_call_3.txt",
        "timezone": "EST",
    },
    "acc_004": {
        "company": "Apex Electrical Solutions",
        "industry": "Electrical",
        "demo_file": "demo_call_4.txt",
        "onboarding_file": "onboard_call_4.txt",
        "timezone": "PST",
    },
    "acc_005": {
        "company": "ClearView Pest Control",
        "industry": "Pest Control",
        "demo_file": "demo_call_5.txt",
        "onboarding_file": "onboard_call_5.txt",
        "timezone": "EST",
    },
}

# ─── Agent Settings ─────────────────────────────────────────────────────────────
DEFAULT_VOICE = "Retell-Cimo"
DEFAULT_LANGUAGE = "en-US"
DEFAULT_CALLBACK_GUARANTEE_MINUTES = 30
TRANSFER_TIMEOUT_SECONDS = 30

# ─── Confidence Thresholds ──────────────────────────────────────────────────────
# Minimum confidence score (0-100) for extraction fields to be considered valid.
MIN_CONFIDENCE = 40

# ─── Pipeline Settings ──────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARN, ERROR
PIPELINE_VERSION = "2.0.0"

# ─── Memo Schema Fields (required for validation) ───────────────────────────────
REQUIRED_MEMO_FIELDS = [
    "account_id",
    "company_name",
    "business_hours",
    "office_address",
    "services_supported",
    "emergency_definition",
    "emergency_routing_rules",
    "non_emergency_routing_rules",
    "call_transfer_rules",
    "integration_constraints",
    "after_hours_flow_summary",
    "office_hours_flow_summary",
    "questions_or_unknowns",
    "notes",
]

REQUIRED_AGENT_FIELDS = [
    "agent_name",
    "version",
    "voice_id",
    "conversationFlow",
    "response_engine",
    "call_transfer_protocol",
    "fallback_protocol",
]

# ─── Colours for Terminal Output ─────────────────────────────────────────────────
class Colors:
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    CYAN    = "\033[96m"
    BOLD    = "\033[1m"
    RESET   = "\033[0m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
