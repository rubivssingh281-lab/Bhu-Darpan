"""Application entrypoint. Starts the FastAPI server."""
import os
import uvicorn

from app.config import settings

if __name__ == "__main__":
    is_render = os.getenv("RENDER", "").lower() in ("1", "true", "yes")
    is_prod = is_render or os.getenv("ENVIRONMENT", "").lower() == "production"

    # Default to auto-reload in local dev, but disable in production/Render to avoid OOM
    reload_env = os.getenv("RELOAD")
    if reload_env is not None:
        reload_enabled = reload_env.lower() in ("1", "true", "yes")
    else:
        reload_enabled = not is_prod

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=reload_enabled,
    )
