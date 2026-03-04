# Clara Retell Automation Pipeline — Makefile
# Run `make help` to see all available commands.

PYTHON := python3
SCRIPTS := scripts

.PHONY: help run run-single clean validate dashboard report all

# ─── Default ────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Clara Retell Automation Pipeline"
	@echo "  ─────────────────────────────────"
	@echo "  make run             Run full pipeline (all 5 accounts)"
	@echo "  make run ACCOUNT=acc_001  Run for a single account"
	@echo "  make validate        Validate all generated outputs"
	@echo "  make dashboard       Generate HTML summary dashboard"
	@echo "  make diff            Generate HTML diff reports"
	@echo "  make tasks           Create/sync task tracker (JSON + HTML)"
	@echo "  make tasks-html      Open task tracker in browser"
	@echo "  make report          Validate + dashboard in one step"
	@echo "  make all             Run pipeline + validate + dashboard + diff"
	@echo "  make clean           Remove all generated outputs"
	@echo "  make n8n             Start n8n via Docker"
	@echo ""

# ─── Pipeline ───────────────────────────────────────────────────────────────────
run:
ifdef ACCOUNT
	$(PYTHON) $(SCRIPTS)/run_pipeline.py --account $(ACCOUNT)
else
	$(PYTHON) $(SCRIPTS)/run_pipeline.py
endif

# ─── Validation ─────────────────────────────────────────────────────────────────
validate:
	$(PYTHON) $(SCRIPTS)/validate.py --verbose

# ─── Diff Reports ───────────────────────────────────────────────────────────────
diff:
	$(PYTHON) $(SCRIPTS)/diff_viewer.py --all

# ─── Dashboard ──────────────────────────────────────────────────────────────────
dashboard:
	$(PYTHON) $(SCRIPTS)/dashboard.py --open

# ─── Combined Report ────────────────────────────────────────────────────────────
report: validate dashboard
	@echo "✓ Validation + Dashboard complete."

# ─── Task Tracker ────────────────────────────────────────────────────────────────
tasks:
	$(PYTHON) $(SCRIPTS)/task_tracker.py --create-all

tasks-html:
	$(PYTHON) $(SCRIPTS)/task_tracker.py --export-html --open

# ─── Full Run ────────────────────────────────────────────────────────────────────
all: run diff validate dashboard
	@echo ""
	@echo "✓ Full pipeline complete."
	@echo "  → Diff reports: outputs/accounts/*/diff_report.html"
	@echo "  → Dashboard:    outputs/reports/dashboard.html"

# ─── n8n ─────────────────────────────────────────────────────────────────────────
n8n:
	docker run -d --rm -p 5678:5678 -e N8N_SECURE_COOKIE=false n8nio/n8n
	@echo "✓ n8n started at http://localhost:5678"
	@echo "  Import: workflows/n8n_pipeline.json"

n8n-stop:
	docker stop $$(docker ps -q --filter ancestor=n8nio/n8n) 2>/dev/null || true
	@echo "✓ n8n stopped."

# ─── Clean ──────────────────────────────────────────────────────────────────────
clean:
	rm -rf outputs/accounts/*/v1
	rm -rf outputs/accounts/*/v2
	rm -f outputs/accounts/*/diff_report.html
	rm -f outputs/reports/dashboard.html
	rm -f changelog/*.md
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true
	@echo "✓ Outputs cleaned."
