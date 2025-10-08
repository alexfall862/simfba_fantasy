# app/processor.py
import os, json, csv, time, hashlib, re
from datetime import datetime
from typing import Dict, Tuple, Any, Optional

import requests

from .config import settings  # needs DATA_ROOT, optional API_BASE, PLAYERS_CSV
from .util import ensure_dir  # mkdir -p helper


# ---------- Helpers ----------

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def _sha256_file(path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb", buffering=1024 * 1024) as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def _yyww(year: int, week: int) -> str:
    yy = str(year % 100).zfill(2)
    ww = str(int(week)).zfill(2)
    return yy + ww

def _start_week_for(sport: str) -> int:
    # NFL: 1..N ; CFB: 0..N
    return 1 if sport == "nfl" else 0

def _player_key_for(sport: str) -> str:
    return "NFLPlayerGameStats" if sport == "nfl" else "CFBPlayerGameStats"

def _team_key_for(sport: str) -> str:
    return "NFLTeamGameStats" if sport == "nfl" else "CFBTeamGameStats"

def _safe_json_load(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ---------- Players CSV path & cache ----------

_players_cache: Optional[Dict[str, Dict[str, Any]]] = None
_players_sha: Optional[str] = None

def _players_csv_path() -> str:
    """
    Resolve players CSV in this order:
      1) settings.PLAYERS_CSV (if provided and exists)
      2) vendored: app/players/playerdetails.csv
      3) fallback under data: {DATA_ROOT}/players/playerdetails.csv
    """
    p = getattr(settings, "PLAYERS_CSV", None)
    if p and os.path.isfile(p):
        return p
    vendored = os.path.join(os.path.dirname(__file__), "players", "playerdetails.csv")
    if os.path.isfile(vendored):
        return vendored
    return os.path.join(settings.DATA_ROOT, "players", "playerdetails.csv")


def _load_players_map() -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    """
    Returns (map, csv_sha).
    map: { "12345": {"FullName": "First Last", "Position": "QB"}, ... }
    """
    global _players_cache, _players_sha
    if _players_cache is not None:
        return _players_cache, _players_sha

    path = _players_csv_path()
    mapping: Dict[str, Dict[str, Any]] = {}
    sha = _sha256_file(path)

    if not os.path.isfile(path):
        print(f"[PROCESSOR] players CSV missing: {path}")
        _players_cache, _players_sha = mapping, sha
        return mapping, sha

    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            _players_cache, _players_sha = mapping, sha
            return mapping, sha

        norm = [("".join(h.split())).lower() for h in header]

        def find_idx(name: str, *alts: str) -> int:
            for n in (name,) + alts:
                if n in norm:
                    return norm.index(n)
            return -1

        i_pid = find_idx("playerid", "id")
        i_fn  = find_idx("firstname", "first")
        i_ln  = find_idx("lastname", "last")
        i_pos = find_idx("position", "pos")

        strict = (i_pid >= 0 and i_fn >= 0 and i_ln >= 0 and i_pos >= 0)

        for row in reader:
            if not row or len(row) < 2:
                continue
            if strict:
                pid = row[i_pid] if i_pid < len(row) else ""
                fn  = row[i_fn]  if i_fn  < len(row) else ""
                ln  = row[i_ln]  if i_ln  < len(row) else ""
                pos = row[i_pos] if i_pos < len(row) else ""
            else:
                # fallback: 0..3
                pid = row[0] if len(row) > 0 else ""
                fn  = row[1] if len(row) > 1 else ""
                ln  = row[2] if len(row) > 2 else ""
                pos = row[3] if len(row) > 3 else ""

            pid = (str(pid) or "").strip()
            if not pid:
                continue

            full = " ".join([str(fn or "").strip(), str(ln or "").strip()]).strip() or None
            pos  = (str(pos or "").strip() or None)

            mapping[pid] = {"FullName": full, "Position": pos}

    print(f"[PROCESSOR] players map size: {len(mapping)}, sha: {sha}")
    _players_cache, _players_sha = mapping, sha
    return mapping, sha


# ---------- Team CSVs (NEW) ----------

_team_maps: Dict[str, Dict[str, Optional[str]]] = {"nfl": None, "cfb": None}  # type: ignore
_team_shas: Dict[str, Optional[str]] = {"nfl": None, "cfb": None}

def _team_csv_path(sport: str) -> str:
    """
    Resolve team CSV path per sport:
      - Prefer vendored: app/teams/<sport>teamids.csv
      - Fallback to data: {DATA_ROOT}/teams/<sport>teamids.csv
    Filenames expected: nflteamids.csv / cfbteamids.csv
    """
    filename = f"{sport}teamids.csv"  # nflteamids.csv / cfbteamids.csv
    vendored = os.path.join(os.path.dirname(__file__), "teams", filename)
    if os.path.isfile(vendored):
        return vendored
    return os.path.join(settings.DATA_ROOT, "teams", filename)


def _load_team_map(sport: str) -> Tuple[Dict[Any, Optional[str]], Optional[str]]:
    """
    Load team_id -> team_abbr/abbrev for the given sport.
    Returns a mapping that supports BOTH str and int keys, e.g. mapping['110'] and mapping[110].
    """
    sport = sport.lower()
    if sport not in ("nfl", "cfb"):
        return {}, None

    # per-run cache
    if _team_maps[sport] is not None:
        return _team_maps[sport], _team_shas[sport]

    path = _team_csv_path(sport)
    mapping: Dict[Any, Optional[str]] = {}
    sha = _sha256_file(path)

    if not os.path.isfile(path):
        print(f"[PROCESSOR] team CSV missing for {sport}: {path}")
        _team_maps[sport], _team_shas[sport] = mapping, sha
        return mapping, sha

    def _add_row(tid_raw, abbr_raw):
        # normalize id & name
        tid_s = (str(tid_raw or "").strip())
        if not tid_s:
            return
        abbr = (str(abbr_raw or "").strip() or None)

        # insert both string and int keys (when possible)
        mapping[tid_s] = abbr
        try:
            tid_i = int(tid_s)
            mapping[tid_i] = abbr
        except ValueError:
            pass

    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        first_line = fh.readline()
        fh.seek(0)

        fl = first_line.strip().lower()
        has_header = ("team_id" in fl) and ("team_abbr" in fl or "team_abbrev" in fl)

        if has_header:
            reader = csv.DictReader(fh)
            # normalize keys (lower, no spaces)
            def nk(k: str) -> str:
                return "".join((k or "").split()).lower()

            for rec in reader:
                rn = {nk(k): v for k, v in rec.items()}
                tid = rn.get("team_id")
                abbr = rn.get("team_abbr")
                if abbr is None:
                    abbr = rn.get("team_abbrev")
                _add_row(tid, abbr)
        else:
            # headerless: assume team_id, team_abbr
            reader = csv.reader(fh)
            for row in reader:
                if not row:
                    continue
                tid = row[0] if len(row) > 0 else ""
                abbr = row[1] if len(row) > 1 else ""
                _add_row(tid, abbr)

    print(f"[PROCESSOR] team map [{sport}] size: {len(mapping)}, sha: {sha}")
    _team_maps[sport], _team_shas[sport] = mapping, sha
    return mapping, sha



# ---------- Process one raw file into processed ----------

def process_one(sport: str, year: int, yyww: str, raw_path: str, force: bool = False) -> str:
    """
    Build processed/{sport}/{year}/{yyww}.json from raw JSON.
    Returns: 'processed' | 'unchanged' | 'error'
    Skips only when processed exists AND both raw hash and CSV hash(es) match,
    unless force=True.
    """
    if not os.path.isfile(raw_path):
        return "error"

    raw_sha = _sha256_file(raw_path)
    players_map, players_sha = _load_players_map()
    teams_map, teams_sha = _load_team_map(sport)

    proc_dir  = os.path.join(settings.DATA_ROOT, "processed", sport, str(year))
    proc_path = os.path.join(proc_dir, f"{yyww}.json")
    meta_path = os.path.join(proc_dir, f"{yyww}.meta.json")
    _ensure_dir(proc_dir)

    # Skip only if not forcing and meta matches
    if (not force) and os.path.isfile(proc_path) and os.path.isfile(meta_path):
        meta = _safe_json_load(meta_path) or {}
        if (
            meta.get("source_sha256") == raw_sha and
            meta.get("players_sha256") == players_sha and
            meta.get("teams_sha256") == teams_sha
        ):
            return "unchanged"

    raw = _safe_json_load(raw_path)
    if not isinstance(raw, dict):
        return "error"

    team_key   = _team_key_for(sport)
    player_key = _player_key_for(sport)

    out = {
        team_key:   raw.get(team_key,   []) or [],
        player_key: raw.get(player_key, []) or [],
        "_computed": {}
    }

    # --- Enrich TEAM rows with Team name from teams_map via TeamID ---
    team_rows = out[team_key]
    if team_rows and isinstance(team_rows, list):
        for trow in team_rows:
            if not isinstance(trow, dict):
                continue
            tid_val = trow.get("TeamID")
            if tid_val is None:
                trow.setdefault("Team", None)
                continue
            tid = str(tid_val).strip()
            trow["Team"] = teams_map.get(tid)  # could be None if not found

    # --- Enrich PLAYER rows with FullName/Position; also Team from TeamID if present ---
    player_rows = out[player_key]
    if player_rows and isinstance(player_rows, list):
        # choose ID key differently for nfl/cfb (you already asked for NFLPlayerID preference)
        if sport == "nfl":
            preferred = ["NFLPlayerID"]
        else:
            preferred = ["CollegePlayerID"]

        # detect fallbacks from actual data
        id_key = None
        if isinstance(player_rows[0], dict):
            for k in preferred:
                if k in player_rows[0]:
                    id_key = k
                    break
            if not id_key:
                for k in player_rows[0].keys():
                    kl = str(k).lower()
                    if kl.endswith("id") and not any(x in kl for x in ["team", "game", "season"]):
                        id_key = k
                        break
        if not id_key:
            id_key = "ID"  # last resort

        for row in player_rows:
            if not isinstance(row, dict):
                continue

            # Player name/position
            pid_val = row.get(id_key)
            pid = str(pid_val).strip() if pid_val is not None else None
            if pid and pid in players_map:
                row["FullName"] = players_map[pid]["FullName"]
                row["Position"] = players_map[pid]["Position"]
            else:
                row.setdefault("FullName", None)
                row.setdefault("Position", None)

            # Team name on player row (if TeamID present)
            tid_val = row.get("TeamID")
            if tid_val is not None:
                tid = str(tid_val).strip()
                row["Team"] = teams_map.get(tid)
            else:
                row.setdefault("Team", None)

    # Write processed content
    try:
        with open(proc_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        return "error"

    # Write meta (best effort)
    meta = {
        "source_sha256": raw_sha,
        "players_sha256": players_sha,
        "teams_sha256": teams_sha,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "source": os.path.relpath(raw_path, settings.DATA_ROOT).replace("\\", "/"),
        "enriched": {
            "team_rows": len(team_rows) if isinstance(team_rows, list) else 0,
            "player_rows": len(player_rows) if isinstance(player_rows, list) else 0,
            "player_with_fullname": sum(1 for r in player_rows if isinstance(r, dict) and r.get("FullName")) if isinstance(player_rows, list) else 0,
            "with_team_name_on_team_rows": sum(1 for r in team_rows if isinstance(r, dict) and r.get("Team")) if isinstance(team_rows, list) else 0,
        }
    }
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return "processed"


# ---------- Write-if-changed for raw ----------

def _write_if_changed(path: str, content_bytes: bytes) -> Tuple[str, Optional[str]]:
    """
    Writes content if hash changed.
    Returns (status, sha256) where status in {'new','updated','unchanged','error'}.
    """
    sha_remote = _sha256_bytes(content_bytes)
    existed = os.path.isfile(path)
    sha_local = _sha256_file(path) if existed else None

    if sha_local and sha_local == sha_remote:
        return ("unchanged", sha_remote)

    try:
        _ensure_dir(os.path.dirname(path))
        with open(path, "wb") as f:
            f.write(content_bytes)
    except Exception:
        return ("error", None)

    return ("updated" if existed else "new", sha_remote)


# ---------- Reprocess RAW -> PROCESSED ----------

def reprocess_raw(
    data_root: str | None = None,
    sport: str | None = None,    # 'nfl' | 'cfb' | None=both
    year: int | None = None,     # specific year or None=all
    force: bool = True,
) -> Dict[str, Any]:
    """
    Walks data/raw and re-runs process_one() to generate data/processed.
    If force=True, meta is ignored via 'force' flag (no skip).
    Returns counts: processed, unchanged, errors.
    """
    root = data_root or settings.DATA_ROOT
    raw_root = os.path.join(root, "raw")
    processed = 0
    unchanged = 0
    errors = 0

    sports = [sport] if sport in ("nfl", "cfb") else ["nfl", "cfb"]

    for sp in sports:
        sp_dir = os.path.join(raw_root, sp)
        if not os.path.isdir(sp_dir):
            continue

        for yname in sorted(os.listdir(sp_dir)):
            if not yname.isdigit():
                continue
            y = int(yname)
            if year is not None and y != year:
                continue

            y_dir = os.path.join(sp_dir, yname)
            if not os.path.isdir(y_dir):
                continue

            for fname in sorted(os.listdir(y_dir)):
                if not fname.endswith(".json"):
                    continue
                m = re.match(r"^(\d{4})\.json$", fname)
                if not m:
                    continue
                yyww = m.group(1)
                raw_path = os.path.join(y_dir, fname)

                st = process_one(sp, y, yyww, raw_path, force=force)
                if st == "processed":
                    processed += 1
                elif st == "unchanged":
                    unchanged += 1
                else:
                    errors += 1

    return {
        "processed": processed,
        "unchanged": unchanged,
        "errors": errors,
        "force": force,
        "sport": sport,
        "year": year,
        "stamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


# ---------- Run sync (download raw + process) ----------

def run_sync(start_year=None, years_ahead=None, max_week=None, api_base=None, data_root=None, rate_limit_ms=350) -> dict:
    """
    Downloads raw JSONs into {DATA_ROOT}/raw/{sport}/{year}/{yyww}.json
    Uses hash to avoid rewriting unchanged files.
    Always attempts to process into {DATA_ROOT}/processed/... afterwards.
    Returns a summary dict.
    """
    SPORTS = ["nfl", "cfb"]

    api = api_base or getattr(settings, "API_BASE", "https://simfba.azurewebsites.net/api/statistics/interface/v2")
    root = data_root or settings.DATA_ROOT
    _ensure_dir(root)

    cy = datetime.utcnow().year
    sy = int(start_year) if start_year is not None else cy
    ahead = int(years_ahead) if years_ahead is not None else 0
    mw = int(max_week) if max_week is not None else 20

    if sy < 2020: sy = 2020
    if ahead < 0: ahead = 0
    if mw < 0: mw = 0
    if mw > 30: mw = 30

    end_year = cy + ahead

    # reset caches per run
    global _players_cache, _players_sha, _team_maps, _team_shas
    _players_cache, _players_sha = None, None
    _team_maps = {"nfl": None, "cfb": None}   # type: ignore
    _team_shas = {"nfl": None, "cfb": None}

    new = updated = unchanged = 0
    proc_new = proc_unchanged = proc_err = 0
    touched_endpoints = []

    for sport in SPORTS:
        for year in range(sy, end_year + 1):
            start_wk = _start_week_for(sport)
            for week in range(start_wk, mw + 1):
                yyww = _yyww(year, week)

                raw_dir = os.path.join(root, "raw", sport, str(year))
                _ensure_dir(raw_dir)
                raw_path = os.path.join(raw_dir, f"{yyww}.json")

                url = f"{api}/{sport}/{year}/{yyww}/WEEK/2"

                body = None
                for attempt in range(3):
                    try:
                        r = requests.get(url, headers={"Accept": "application/json"}, timeout=20)
                        if r.status_code == 200:
                            body = r.content
                            break
                        else:
                            body = None
                            break
                    except requests.RequestException:
                        time.sleep(0.7 * (2 ** attempt))
                        continue

                if body is None:
                    continue

                status, sha = _write_if_changed(raw_path, body)
                if status == "new":
                    new += 1
                    touched_endpoints.append(f"/{sport}/{year}/{yyww}/WEEK/2")
                elif status == "updated":
                    updated += 1
                    touched_endpoints.append(f"/{sport}/{year}/{yyww}/WEEK/2")
                elif status == "unchanged":
                    unchanged += 1
                else:
                    continue

                pst = process_one(sport, year, yyww, raw_path)
                if pst == "processed":
                    proc_new += 1
                elif pst == "unchanged":
                    proc_unchanged += 1
                else:
                    proc_err += 1

                time.sleep(rate_limit_ms / 1000.0)

    stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    return {
        "stamp": stamp,
        "new": new,
        "updated": updated,
        "unchanged": unchanged,
        "processed_new": proc_new,
        "processed_unchanged": proc_unchanged,
        "processed_error": proc_err,
        "updated_endpoints": touched_endpoints,
        "start_year": sy,
        "end_year": end_year,
        "max_week": mw,
    }
