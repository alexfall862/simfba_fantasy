import os
from fastapi import APIRouter, Depends, HTTPException, Request, status

router = APIRouter(tags=["admin"])

RUN_TOKEN = os.getenv("RUN_TOKEN")

def require_admin(request: Request):
    if not RUN_TOKEN:
        raise HTTPException(status_code=500, detail="RUN_TOKEN not set on server")
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = auth.split(" ", 1)[1].strip()
    if token != RUN_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

@router.post("/run", dependencies=[Depends(require_admin)])
async def run_sync():
    # TODO: call your real sync job here
    return {"ok": True, "msg": "sync started"}
