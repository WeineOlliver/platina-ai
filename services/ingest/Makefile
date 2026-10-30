# services/ingest/Makefile - Pipeline Runner for services/ingest

.PHONY: rebuild test-pipeline

GAME ?= the-witcher-3-wild-hunt

rebuild:
	PYTHONPATH=. .venv/bin/python -m src.pipeline.run --game $(GAME) --stage all

test-pipeline:
	.venv/bin/pytest tests/pipeline -v
