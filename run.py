"""Root entrypoint to allow starting the backend from repository root."""
import os
import sys
from pathlib import Path

# Add Backend to sys.path so 'app' and 'ingest' can be imported when running from repo root
BASE_DIR = Path(__file__).resolve().parent / "Backend"
if BASE_DIR.exists() and str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
    os.chdir(BASE_DIR)

import uvicorn
from app.config import settings

if __name__ == "__main__":
    port = int(os.getenv("PORT", settings.port))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
