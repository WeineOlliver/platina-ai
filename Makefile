# Makefile - Platina AI Automation & Pipeline Runner

.PHONY: rebuild test-pipeline

GAME ?= the-witcher-3-wild-hunt

# Rebuild entire pipeline for a target game (parse -> link -> check -> chunk -> load)
rebuild:
	cd services/ingest && PYTHONPATH=. .venv/bin/python -m src.pipeline.run --game $(GAME) --stage all

# Run pipeline unit tests
test-pipeline:
	cd services/ingest && .venv/bin/pytest tests/pipeline -v
