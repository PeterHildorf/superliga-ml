

#make setup      opretter venv + installerer pakker
#make ingest     kører src/ingest.py i venv
#make run SCRIPT=src/test_superliga.py

# ----- meget simpel, virker på macOS/Linux og Windows (Git Bash/PowerShell) -----
ifeq ($(OS),Windows_NT)
  PY ?= py
  VENV_PY := .venv\Scripts\python.exe
  ACT := .\.venv\Scripts\Activate.ps1
else
  PY ?= python3
  VENV_PY := .venv/bin/python
  ACT := source .venv/bin/activate
endif

.DEFAULT_GOAL := help

venv: ## Opret venv hvis den ikke findes
	@if [ ! -d ".venv" ]; then $(PY) -m venv .venv; echo "✅ venv oprettet"; else echo "✅ venv findes allerede"; fi

install: venv ## Installer requirements i venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -r requirements.txt

setup: install ## Én kommando: venv + install
	@echo ""; echo "✅ Klar. Aktivér miljø næste gang med:"; echo "   $(ACT)"

ingest: ## Kør din ingestion
	$(VENV_PY) src/ingest.py

run: ## Kør vilkårligt script: make run SCRIPT=src/test_superliga.py
	@if [ -z "$(SCRIPT)" ]; then echo "Brug: make run SCRIPT=sti/til/fil.py"; exit 1; fi
	$(VENV_PY) $(SCRIPT)

clean: ## Slet caches/pyc
	rm -rf __pycache__ */__pycache__ .pytest_cache *.pyc

help: ## Vis mål
	@echo "Mål:"
	@echo "  make setup     - opret venv og installer requirements"
	@echo "  make ingest    - kør src/ingest.py"
	@echo "  make run SCRIPT=... - kør vilkårligt Python-script i venv"
	@echo "  make clean     - ryd op"
