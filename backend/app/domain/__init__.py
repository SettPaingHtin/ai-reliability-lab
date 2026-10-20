"""Framework-free domain logic: scoring, JSONL parsing, providers, evaluation engine.

Nothing in this package imports FastAPI, SQLAlchemy, or any I/O library, so it can be
tested in isolation and reused by the CLI and background workers.
"""
