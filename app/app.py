# app.py
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict
import os

from config import DATA_ROOT, RUN_TOKEN, START_YEAR, YEARS_AHEAD, MAX_WEEK, RATE_LIMIT_MS
from sync import run_sync

app = FastAPI(title="SimFBA Sync JSON")

# Serve files (raw + processed) at /data
os.makedirs(DATA_ROOT, exist_ok=True)
app.mount("/data", StaticFiles(directory=DATA_ROOT), name="data")

def admin_guard(req: Request):
    auth = req.headers.get("authorization","")
    if not RUN_TOKEN:
        raise HTTPException(500, detail="RUN_TOKEN not set on server")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, detail="Missing bearer token")
    token = auth.split(" ",1)[1].strip()
    if token != RUN_TOKEN:
        raise HTTPException(403, detail="Invalid token")
    return True

@app.post("/admin/run-sync")
def admin_run_sync(payload: Dict = {}, _=Depends(admin_guard)):
    # Allow overrides from payload (optional)
    start_year  = int(payload.get("start_year",  START_YEAR))
    years_ahead = int(payload.get("years_ahead", YEARS_AHEAD))
    max_week    = int(payload.get("max_week",    MAX_WEEK))
    rate_ms     = int(payload.get("rate_limit_ms", RATE_LIMIT_MS))

    stats = run_sync(
        start_year=start_year,
        years_ahead=years_ahead,
        max_week=max_week,
        rate_limit_ms=rate_ms,
    )
    return {"ok": True, **stats}

@app.get("/manifest")
def manifest():
    """
    Returns a manifest of processed files, grouped by sport/year/week,
    with URLs you can feed straight into your viewer.
    """
    out = {"files":{}, "years":{}, "weeks":{}, "defaults":{"sport":"nfl","view":"team"}}
    for sport in ("nfl","cfb"):
        out["files"][sport] = {}
        out["years"][sport] = []
        out["weeks"][sport] = {}
        sport_root = os.path.join(DATA_ROOT, "processed", sport)
        if not os.path.isdir(sport_root): continue
        years = sorted([int(y) for y in os.listdir(sport_root) if y.isdigit()])
        out["years"][sport] = years
        for y in years:
            ydir = os.path.join(sport_root, str(y))
            out["files"][sport][y] = {}
            out["weeks"][sport][y] = []
            for name in os.listdir(ydir):
                if not name.endswith(".json"): continue
                if len(name) != 9: continue        # "YYWW.json" = 4+5
                yyww = name[:4]
                week = int(yyww[2:4])
                out["weeks"][sport][y].append(week)
                out["files"][sport][y][yyww] = f"/data/processed/{sport}/{y}/{yyww}.json"
            out["weeks"][sport][y].sort()
    # choose latest NFL if present
    nfl_years = out["years"].get("nfl") or []
    if nfl_years:
        last = nfl_years[-1]
        out["defaults"]["year"] = last
        w = out["weeks"]["nfl"].get(last) or []
        if w: out["defaults"]["week"] = w[-1]
    else:
        cfb_years = out["years"].get("cfb") or []
        if cfb_years:
            out["defaults"]["sport"] = "cfb"
            last = cfb_years[-1]
            out["defaults"]["year"] = last
            w = out["weeks"]["cfb"].get(last) or []
            if w: out["defaults"]["week"] = w[-1]

    return out
