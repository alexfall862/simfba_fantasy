from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from ..config import settings
from ..manifest import build_manifest

router = APIRouter()

@router.get("/health")
def health():
    return {"ok": True}

@router.get("/manifest")
def get_manifest():
    # Build URLs that match the routes below (NOT the StaticFiles mount)
    # If you prefer StaticFiles under /data, say so and I’ll give that variant.
    return build_manifest(
        data_root=settings.DATA_ROOT,
        data_url_prefix="",               # we’ll generate /data/processed/... manually below
        default_sport="nfl",
        use_api_routes=True               # <-- we’ll implement this next in manifest.py
    )

@router.get("/data/processed/{sport}/{year}/{yyww}.json")
def get_processed(sport: str, year: int, yyww: str):
    if sport not in ("nfl", "cfb"):
        raise HTTPException(404, detail="bad sport")
    path = Path(settings.DATA_ROOT) / "processed" / sport / str(year) / f"{yyww}.json"
    if not path.is_file():
        # include the resolved path in the detail for easy debugging
        raise HTTPException(404, detail=f"missing: {path}")
    return FileResponse(path)

@router.get("/data/raw/{sport}/{year}/{yyww}.json")
def get_raw(sport: str, year: int, yyww: str):
    if sport not in ("nfl", "cfb"):
        raise HTTPException(404, detail="bad sport")
    path = Path(settings.DATA_ROOT) / sport / str(year) / f"{yyww}.json"
    if not path.is_file():
        raise HTTPException(404, detail=f"missing: {path}")
    return FileResponse(path)

@router.get("/debug/which-file")
def which_file(
    kind: str = Query("processed", regex="^(processed|raw)$"),
    sport: str = Query("nfl", regex="^(nfl|cfb)$"),
    year: int = 2025,
    yyww: str = "2503",
):
    base = Path(settings.DATA_ROOT)
    path = (base / "processed" / sport / str(year) / f"{yyww}.json") if kind == "processed" \
           else (base / sport / str(year) / f"{yyww}.json")
    return {"path": str(path), "exists": path.is_file()}

@router.get("/debug/ls")
def debug_ls():
    p = Path(settings.DATA_ROOT) / "processed" / "nfl" / "2025"
    return {
        "DATA_ROOT": settings.DATA_ROOT,
        "exists": p.exists(),
        "listed": sorted([f.name for f in p.glob("*.json")])[:10]
    }