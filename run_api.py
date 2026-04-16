import os

import uvicorn

if __name__ == "__main__":
    # reload=True spawns a parent + worker; on Windows multiple stray `run_api.py`
    #  surreal start --log info --user root --pass root rocksdb:./surreal_data/mydb.db
    # instances also bind :5055 and can serve stale code. Default: single process.
    reload = os.getenv("UVICORN_RELOAD", "").strip().lower() in ("1", "true", "yes")
    # Railway / Render 等会注入 PORT；本地仍用 API_PORT 或默认 5055
    port = int(os.getenv("PORT", os.getenv("API_PORT", "5055")))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=reload)
