# API Contract Notes (Starter)

This folder is the placeholder for the generated OpenAPI spec or source contract files.

Initial source-of-truth options:

1. FastAPI-generated OpenAPI (`backend/app/main.py`)
2. Hand-authored OpenAPI YAML, then generate backend/frontend types
3. Shared JSON Schema + codegen for both Python and TypeScript

Current scaffold uses:

- Python Pydantic models in `backend/app/models/contracts.py`
- JSON Schemas in `shared/schemas/`

