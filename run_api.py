import os

import uvicorn

if __name__ == "__main__":
    # reload=True spawns a parent + worker; on Windows multiple stray `run_api.py`
    # instances also bind :5055 and can serve stale code. Default: single process.
    reload = os.getenv("UVICORN_RELOAD", "").strip().lower() in ("1", "true", "yes")
    port = int(os.getenv("API_PORT", "5055"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=reload)
