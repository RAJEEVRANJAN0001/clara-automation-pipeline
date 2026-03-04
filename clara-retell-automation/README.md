# Clara Retell Automation Pipeline

> **Zero-Cost Automation Pipeline**: Demo Call → Retell Agent Draft → Onboarding Updates → Agent Revision

---

## What Is This?

An automated system that takes service company phone call transcripts and turns them into AI phone receptionist agents for [Retell AI](https://www.retellai.com/). It processes **5 demo calls + 5 onboarding calls** across two pipelines — no paid APIs needed.

**Key features:**
- **Rule-based NLP extraction** — regex pipelines with per-field confidence scoring
- **Two-stage versioning** — v1 (demo) → v2 (onboarding) with changelogs and visual diffs
- **Retell-compatible** agent specs with `conversationFlow`, 9 nodes, and `global_prompt`
- **n8n workflow** included (10-node Code-based pipeline)
- **Task tracker** — zero-cost Asana-style assignment management
- **Audio pipeline** — `.m4a` recordings generated via macOS `say` + `afconvert`
- **Docker** support for n8n orchestration
- **Validation suite** — checks all memos, specs, and changelogs automatically

---

## Pipeline Overview

```
Demo Call Transcript
        │
        ▼
  Pipeline A: extract_account_info.py
        │
        ├─► memo.json (v1)          ← structured account data
        └─► agent_spec.json (v1)    ← Retell-ready agent config

Onboarding Call Transcript
        │
        ▼
  Pipeline B: update_account.py
        │
        ├─► memo.json (v2)          ← updated account data
        ├─► agent_spec.json (v2)    ← revised agent config
        └─► changelog.md            ← human-readable diff
```

**Pipeline A** (Demo Call → v1): Reads a demo call transcript and extracts business hours, services, emergency routing, call transfer rules, integration constraints, and more — then generates a structured memo and Retell agent spec.

**Pipeline B** (Onboarding Call → v2): Reads an onboarding call transcript, detects updates, applies them to the v1 memo, and produces a v2 memo, v2 agent spec, and a markdown changelog.

---

## Accounts Processed

| Account ID | Company | v1 Confidence | v2 Confidence |
|------------|---------|:-------------:|:-------------:|
| acc\_001 | ABC Plumbing | 95% | 97% |
| acc\_002 | Sunshine HVAC Services | 95% | 95% |
| acc\_003 | GreenLeaf Landscaping | 86% | 89% |
| acc\_004 | Apex Electrical Solutions | 94% | 94% |
| acc\_005 | ClearView Pest Control | 96% | 96% |

---

## Project Structure

```
clara-retell-automation/
│
├── scripts/
│   ├── config.py                # Centralized config, ACCOUNT_MAP, paths
│   ├── transcribe.py            # Reads .txt or runs Whisper on .m4a audio
│   ├── extract_account_info.py  # Regex extraction + confidence scoring
│   ├── update_account.py        # Applies onboarding updates to v1 memo
│   ├── generate_agent_spec.py   # Builds Retell-compatible agent_spec.json
│   ├── validate.py              # Validates memos, specs, and changelogs
│   ├── diff_viewer.py           # Generates HTML visual diff reports
│   ├── dashboard.py             # Outputs HTML summary dashboard
│   ├── task_tracker.py          # Zero-cost task/assignment tracker
│   └── run_pipeline.py          # Master orchestrator — runs all accounts
│
├── dataset/
│   ├── demo_calls/
│   │   ├── demo_call_1.txt      # Demo call transcripts (acc_001–005)
│   │   └── audio/
│   │       └── demo_call_1.m4a  # Audio files generated via macOS TTS
│   └── onboarding_calls/
│       ├── onboard_call_1.txt   # Onboarding call transcripts (acc_001–005)
│       └── audio/
│           └── onboard_call_1.m4a
│
├── outputs/
│   ├── accounts/
│   │   └── acc_001/
│   │       ├── v1/
│   │       │   ├── memo.json        # Extracted account data
│   │       │   └── agent_spec.json  # Retell agent configuration
│   │       ├── v2/
│   │       │   ├── memo.json
│   │       │   └── agent_spec.json
│   │       └── diff_report.html     # Visual diff (v1 vs v2)
│   └── reports/
│       ├── dashboard.html       # HTML summary of all accounts
│       └── tasks.html           # Task tracker HTML report
│
├── changelog/
│   └── acc_001_changes.md       # Per-account v1→v2 change logs
│
├── workflows/
│   └── n8n_pipeline.json        # n8n workflow (10 Code nodes)
│
├── docker-compose.yml           # Docker config for n8n
├── requirements.txt
├── Makefile
└── README.md
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the full pipeline

```bash
python3 scripts/run_pipeline.py
```

This processes all 5 accounts (Pipeline A + B each) and outputs memos, agent specs, changelogs, visual diffs, and HTML reports.

### 3. Run validation

```bash
python3 scripts/validate.py --verbose
```

Expected output:
```
  PASS  acc_001 (ABC Plumbing)
  PASS  acc_002 (Sunshine HVAC Services)
  PASS  acc_003 (GreenLeaf Landscaping)
  PASS  acc_004 (Apex Electrical Solutions)
  PASS  acc_005 (ClearView Pest Control)

  Accounts validated : 5
  Passed             : 5
  Failed             : 0
  Total errors       : 0
  Total warnings     : 0
```

### 4. Open the dashboard

```bash
python3 scripts/dashboard.py
```

Opens `outputs/reports/dashboard.html` in your browser.

---

## Using the Makefile

```bash
make run        # Run full pipeline
make validate   # Run validation suite
make dashboard  # Open HTML dashboard
make diff       # Generate visual diff reports
make clean      # Remove output files
```

---

## Individual Scripts

### Pipeline A — Extract from demo call

```bash
python3 scripts/run_pipeline.py --account acc_001 --pipeline A
```

### Pipeline B — Apply onboarding updates

```bash
python3 scripts/update_account.py \
  dataset/onboarding_calls/onboard_call_1.txt \
  --account-id acc_001 \
  --v1-memo outputs/accounts/acc_001/v1/memo.json \
  --output-dir outputs/accounts/acc_001/v2/
```

### Transcribe audio (requires Whisper)

```bash
python3 scripts/transcribe.py dataset/demo_calls/audio/demo_call_1.m4a
```

---

## Confidence Scoring

Each extracted memo includes a per-field confidence score:

| Field | Scoring Logic |
|-------|--------------|
| `business_hours` | Required fields only (days, start, end, timezone) |
| `emergency_routing` | Weighted: primary\_phone=35, callback=30, contact=20, backup=10 |
| `call_transfer_rules` | Weighted: fail\_protocol=50, timeout\_action=30, max\_rings=20 |
| `integration_constraints` | 1 system=70, 2 systems=90, 3+ systems=100 |
| `services_supported` | `min(len × 25, 100)` |

The `overall` score is the average across all fields. Any field scoring below 50% automatically generates a question in `questions_or_unknowns` for human review.

---

## Agent Spec Format

Each generated `agent_spec.json` is Retell-compatible and includes:

```json
{
  "agent_name": "Clara – ABC Plumbing",
  "version": "2.0.0",
  "voice_id": "Retell-Cimo",
  "language": "en-US",
  "conversationFlow": {
    "global_prompt": "...",
    "nodes": [ "..." ],
    "edges": [ "..." ]
  },
  "call_transfer_protocol": {},
  "fallback_protocol": {},
  "response_engine": {}
}
```

The `conversationFlow` contains **9 nodes**: Greeting, Identify Caller, Collect Info, Check Hours, Handle Emergency, Schedule Callback, Transfer Call, Leave Message, and End Call.

---

## n8n Workflow

The `workflows/n8n_pipeline.json` provides the same pipeline as a visual n8n workflow with **10 Code nodes**:

1. **Load Account Config** — Reads `ACCOUNT_MAP` from config
2. **Read Transcript** — Loads `.txt` transcript
3. **Extract Account Info** — Runs regex extraction pipeline
4. **Compute Confidence** — Field-specific weighted scoring
5. **Generate Questions** — Flags low-confidence fields
6. **Build Memo v1** — Assembles structured memo JSON
7. **Build Agent Spec v1** — Generates Retell-compatible spec
8. **Apply Onboarding Updates** — Merges v2 changes
9. **Build Agent Spec v2** — Regenerates spec from v2 memo
10. **Export Outputs** — Saves all files and generates changelog

### Run with Docker

```bash
docker-compose up -d
# Open http://localhost:5678
# Import workflows/n8n_pipeline.json
# Click Execute Workflow
```

> All nodes use embedded JavaScript — no external API keys required.

---

## Requirements

```
openai-whisper   # Optional: only needed for audio transcription
```

All other dependencies are Python 3.9+ standard library. No OpenAI API key needed.

---

## Validation Checks

`validate.py` checks every account output for:

- [x] `memo.json` exists for v1 and v2
- [x] `agent_spec.json` exists for v1 and v2
- [x] `changelog.md` exists
- [x] Required memo fields present (company\_name, services\_supported, business\_hours, etc.)
- [x] Required agent spec fields present (agent\_name, version, voice\_id, conversationFlow, call\_transfer\_protocol, fallback\_protocol)
- [x] `services_supported` is non-empty
- [x] `questions_or_unknowns` is populated
- [x] v2 memo updated relative to v1 (improvement check)
- [x] Extraction confidence `overall` >= 50

---

## Retell Setup Guide

### Creating a Retell Account

1. Go to [https://www.retellai.com](https://www.retellai.com) and sign up for a free account
2. After logging in, navigate to **Settings → API Keys** and copy your API key
3. Note: If the free tier does not allow programmatic agent creation, follow the manual import steps below

### Importing the Agent Spec into Retell

Each generated `agent_spec.json` is designed to match Retell's agent configuration format. To deploy an agent manually:

1. Open the Retell Dashboard → **Agents** → **Create New Agent**
2. Set **Agent Name** to the value from `agent_name` (e.g. "ABC Plumbing Assistant")
3. Set **Voice** to the value from `voice_id` (e.g. "Retell-Cimo")
4. Set **Language** to `en-US`
5. Under **Conversation Flow**, paste the contents of `conversationFlow.global_prompt` as the system prompt
6. Configure **Call Transfer**:
   - Set the transfer number from `call_transfer_protocol.transfer_number`
   - Set max rings / timeout from `call_transfer_protocol.max_rings`
7. Configure **Fallback** behavior using the text from `fallback_protocol`
8. Set **Variables** from the `variables` section (business\_hours, emergency\_routing, office\_address)
9. Save and publish the agent

### Using with the Retell API (if available)

```bash
# Example: Create agent via API (requires paid tier)
curl -X POST https://api.retellai.com/v2/create-agent \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @outputs/accounts/acc_001/v2/agent_spec.json
```

> Since Retell's free tier may not support API-based agent creation, the pipeline outputs offline-ready spec files that can be manually imported via the steps above.

---

## Known Limitations

1. **Regex-based extraction** — The extraction pipeline uses pattern matching (not LLM), which may miss unusual phrasings, abbreviations, or non-standard transcript formats
2. **No live Retell API integration** — Agent specs are generated as offline JSON files; deploying to Retell requires manual import or a paid API tier
3. **Audio transcription requires Whisper** — The `.m4a` audio files can only be transcribed if `openai-whisper` is installed locally; the pipeline primarily uses `.txt` transcripts
4. **Single-language support** — Currently configured for `en-US` only; multilingual transcripts are not handled
5. **Confidence scoring is heuristic** — Field-specific weights are tuned for the demo dataset and may not generalize to all service industries
6. **No real-time processing** — The pipeline runs as a batch job; there is no webhook-triggered or streaming mode
7. **Task tracker is file-based** — Uses local JSON storage rather than a real project management API (Asana, Jira, etc.)

---

## What We Would Improve with Production Access

1. **LLM-powered extraction** — Replace regex patterns with GPT-4 or Claude for higher extraction accuracy, especially for ambiguous or complex transcripts
2. **Retell API integration** — Auto-deploy agents directly to Retell via their API, eliminating manual import steps
3. **Real-time Whisper transcription** — Stream audio → Whisper → extraction pipeline with no manual transcript step
4. **Webhook-driven n8n triggers** — Replace manual execution with webhook nodes that trigger on new file uploads or form submissions
5. **Database-backed storage** — Move from JSON files to Supabase or PostgreSQL for proper querying, versioning, and multi-user access
6. **Automated testing** — Build test suites that validate extraction quality against known ground-truth transcripts
7. **Multi-language support** — Extend extraction patterns and agent prompts for Spanish, French, and other languages
8. **Production monitoring** — Add logging, error alerting, and metrics dashboards for pipeline health
9. **Asana/Jira integration** — Replace the file-based task tracker with real API calls to project management tools
10. **Agent performance feedback loop** — Collect call outcomes from Retell and feed them back to improve extraction and prompt quality

---

## License

MIT
