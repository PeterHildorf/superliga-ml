

#make setup      opretter venv + installerer pakker
#make ingest     kører src/ingest.py i venv
#make run SCRIPT=src/test_superliga.py

# ----- meget simpel, virker på macOS/Linux og Windows (Git Bash/PowerShell) -----
ifeq ($(OS),Windows_NT)
  # Windows (PowerShell/Command Prompt)
  PY       ?= py
  VENV_PY   = .venv\Scripts\python.exe
  SHELL     = cmd
else
  # macOS / Linux
  PY       ?= python3
  VENV_PY   = .venv/bin/python
  SHELL     = /bin/bash
endif

.DEFAULT_GOAL := help

venv: ## Opret venv hvis den ikke findes
ifeq ($(OS),Windows_NT)
	if not exist ".venv" ( $(PY) -m venv .venv & echo ✅ venv oprettet ) else ( echo ✅ venv findes allerede )
else
	@if [ ! -d ".venv" ]; then $(PY) -m venv .venv && echo "✅ venv oprettet"; else echo "✅ venv findes allerede"; fi
endif

install: venv ## Installer requirements i venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -r requirements.txt

setup: install ## Én kommando: venv + install
	@echo && echo "✅ Klar. Aktivér miljø næste gang med:"
ifeq ($(OS),Windows_NT)
	@echo "   .\.venv\Scripts\Activate.ps1"
else
	@echo "   source .venv/bin/activate"
endif

ingest: ## Kør din ingestion
ifeq ($(OS),Windows_NT)
	$(VENV_PY) src\ingest.py
else
	$(VENV_PY) src/ingest.py
endif

run: ## Kør vilkårligt script: make run SCRIPT=src/test_superliga.py
ifeq ($(OS),Windows_NT)
	@if not defined SCRIPT ( echo Brug: make run SCRIPT=sti\til\fil.py & exit 1 )
	$(VENV_PY) $(SCRIPT)
else
	@if [ -z "$(SCRIPT)" ]; then echo "Brug: make run SCRIPT=sti/til/fil.py"; exit 1; fi
	$(VENV_PY) $(SCRIPT)
endif

clean: ## Fjern caches/pyc
ifeq ($(OS),Windows_NT)
	del /q /s *.pyc 2>nul & rmdir /q /s __pycache__ 2>nul & rmdir /q /s .pytest_cache 2>nul
else
	rm -rf __pycache__ */__pycache__ .pytest_cache *.pyc
endif

help: ## Vis mål
	@echo Mål:
	@echo "  make setup     - opret venv og installer requirements"
	@echo "  make ingest    - kør src/ingest.py"
	@echo "  make run SCRIPT=... - kør vilkårligt Python-script i venv"
	@echo "  make clean     - ryd op"
