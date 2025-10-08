# app/manifest.py
import os
from typing import Dict, Any, List

def _safe_int(s: str) -> int | None:
    try:
        return int(s)
    except Exception:
        return None

def build_manifest(
    data_root: str,
    data_url_prefix: str = "/data",
    default_sport: str = "nfl",
    use_api_routes: bool = False,   # if True, build /data/processed/{...}.json (your API routes)
) -> Dict[str, Any]:
    """
    Scans PROCESSED and returns:
      {
        sports: ["nfl","cfb"],
        files:  { sport: { year: { "yyww": "<url>" } } },
        years:  { sport: [years...] },
        weeks:  { sport: { year: [weeks...] } },
        defaults: { sport, view, year, week }
      }
    """
    processed_root = os.path.join(data_root, "processed")
    manifest: Dict[str, Any] = {
        "sports": [],
        "files": {},
        "years": {},
        "weeks": {},
        "defaults": {"sport": default_sport, "view": "team"},
    }

    if not os.path.isdir(processed_root):
        return manifest

    for sport in ("nfl", "cfb"):
        sport_dir = os.path.join(processed_root, sport)
        if not os.path.isdir(sport_dir):
            continue

        manifest["sports"].append(sport)
        manifest["files"][sport] = {}
        manifest["years"][sport] = []
        manifest["weeks"][sport] = {}

        for name in sorted(os.listdir(sport_dir)):
            if not name.isdigit():
                continue
            year_i = _safe_int(name)
            if year_i is None:
                continue

            year_dir = os.path.join(sport_dir, name)
            if not os.path.isdir(year_dir):
                continue

            manifest["years"][sport].append(year_i)
            manifest["files"][sport][year_i] = {}
            manifest["weeks"][sport][year_i] = []

            for fname in sorted(os.listdir(year_dir)):
                if not fname.endswith(".json"):
                    continue
                base = fname[:-5]
                if len(base) != 4 or not base.isdigit():
                    continue
                yyww = base
                week = _safe_int(yyww[2:4])
                if week is None:
                    continue

                if use_api_routes:
                    # Match the explicit file endpoints we defined above
                    url = f"/data/processed/{sport}/{year_i}/{yyww}.json"
                else:
                    # Use StaticFiles mount style
                    url = f"{data_url_prefix}/processed/{sport}/{year_i}/{yyww}.json"

                manifest["files"][sport][year_i][yyww] = url
                manifest["weeks"][sport][year_i].append(week)

            manifest["weeks"][sport][year_i].sort()

        manifest["years"][sport].sort()

    chosen_sport = (
        default_sport if manifest["years"].get(default_sport)
        else (manifest["sports"][0] if manifest["sports"] else default_sport)
    )
    manifest["defaults"]["sport"] = chosen_sport

    ys: List[int] = manifest["years"].get(chosen_sport, [])
    if ys:
        last_year = ys[-1]
        manifest["defaults"]["year"] = last_year
        ws = manifest["weeks"].get(chosen_sport, {}).get(last_year, [])
        if ws:
            manifest["defaults"]["week"] = ws[-1]

    return manifest
