import os

import uvicorn


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    reload_enabled = os.environ.get("UVICORN_RELOAD", "false").lower() == "true"
    uvicorn.run("app:app", host=host, port=port, reload=reload_enabled)
