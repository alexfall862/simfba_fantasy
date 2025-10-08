from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import public, admin
from pathlib import Path
from starlette.middleware.proxy_headers import ProxyHeadersMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware


from dotenv import load_dotenv; load_dotenv()
import os
RUN_TOKEN = os.getenv("RUN_TOKEN")

from fastapi import FastAPI
from .routes_admin import router as admin_router

app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.add_middleware(HTTPSRedirectMiddleware)

# Make sure DATA_ROOT exists BEFORE you mount it
os.makedirs(settings.DATA_ROOT, exist_ok=True)

# --- DEBUG: print what we're about to mount
print("[startup] DATA_ROOT =", settings.DATA_ROOT)
print("[startup] DATA_URL_PREFIX =", settings.DATA_URL_PREFIX)
print("[startup] DATA_ROOT exists? ", Path(settings.DATA_ROOT).exists())

app.mount(
    settings.DATA_URL_PREFIX,  # should be "/data"
    StaticFiles(directory=settings.DATA_ROOT),  # absolute path to the "data" folder
    name="data",
)
app.include_router(public.router)
app.include_router(admin_router)


for r in app.routes:
    try:
        print("route:", getattr(r, "path", r))
    except Exception:
        pass

# (Optional) CORS if your admin page is served from another origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_methods=["*"],
    allow_headers=["*"],
)

app = FastAPI(title="SimFBA Python Worker", version="0.2.0")

# Health check
@app.get("/health")
def health():
    return {"ok": True}

# Include the admin routes at /admin/...
app.include_router(admin_router, prefix="/admin")

# Debug: list routes at startup
@app.on_event("startup")
async def list_routes():
    print("== Registered routes ==")
    for r in app.routes:
        methods = ",".join(sorted(r.methods)) if hasattr(r, "methods") else ""
        print(f"{methods:10s} {getattr(r, 'path', getattr(r, 'path_format', ''))}")
    print("========================")

# APIs
app.include_router(public.router, tags=["public"])
app.include_router(admin.router, tags=["admin"])

# Static + Templates
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory="app/templates")

# Public viewer
@app.get("/", response_class=HTMLResponse)
def viewer_page(request: Request):
    return templates.TemplateResponse("viewer.html", {"request": request})

# Admin console
@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    # Admin is token-protected at the API layer; this page just provides UI
    return templates.TemplateResponse("admin.html", {"request": request})

#launch
if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("PORT", "8000"))  # Railway sets PORT; default 8000 locally
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)

import sys
print(f"[BOOT] PORT={os.getenv('PORT')}", file=sys.stderr)
print(f"[BOOT] DATA_ROOT={settings.DATA_ROOT} exists={os.path.isdir(settings.DATA_ROOT)}", file=sys.stderr)
