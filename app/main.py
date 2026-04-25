"""Minimal FastAPI entry point placeholder for the future local PoC."""

try:
    from fastapi import FastAPI
except ImportError:  # pragma: no cover
    FastAPI = None


if FastAPI:
    app = FastAPI(title="Tax Authority RAG PoC", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}
else:
    app = None

