from __future__ import annotations

import sys
from pathlib import Path

import uvicorn


def main() -> None:
    backend_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(backend_dir))
    from app.main import app  # noqa: WPS433

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
