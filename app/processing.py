# app/processing.py
import json, os, hashlib
from datetime import datetime
from .config import settings

PLAYERS_CSV = os.path.join(settings.DATA_ROOT, "players", "playerdetails.csv")

def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256(); h.update(b); return h.hexdigest()

def _sha256_file(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb", buffering=1024*1024) as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _load_players_map() -> tuple[dict, str | None]:
    """
    Returns: (id-> {FullName, Position}, csv_sha256 or None)
    Last-row-wins, tolerant to header names (Player ID, First Name, Last Name, Position).
    """
    import csv
    m: dict[str, dict] = {}
    if not os.path.isfile(PLAYERS_CSV):
        return m, None

    csv_sha = _sha256_file(PLAYERS_CSV)

    with open(PLAYERS_CSV, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return m, csv_sha

        # normalize header
        idx = {"pid": -1, "fn": -1, "ln": -1, "pos": -1}
        if header:
            for i, h in enumerate(header):
                k = (h or "").strip().lower().replace(" ", "")
                if k in ("playerid", "id"): idx["pid"] = i
                elif k == "firstname":       idx["fn"]  = i
                elif k == "lastname":        idx["ln"]  = i
                elif k == "position":        idx["pos"] = i

        strict = all(v >= 0 for v in idx.values())

        for row in reader:
            if not row: continue
            if strict:
                pid = (row[idx["pid"]] if idx["pid"] >= 0 else "").strip()
                fn  = (row[idx["fn"]]  if idx["fn"]  >= 0 else "").strip()
                ln  = (row[idx["ln"]]  if idx["ln"]  >= 0 else "").strip()
                pos = (row[idx["pos"]] if idx["pos"] >= 0 else "").strip()
            else:
                # fallback by position
                pid = (row[0] if len(row) > 0 else "").strip()
                fn  = (row[1] if len(row) > 1 else "").strip()
                ln  = (row[2] if len(row) > 2 else "").strip()
                pos = (row[3] if len(row) > 3 else "").strip()
            if not pid:
                continue
            full = (fn + " " + ln).strip() or None
            m[pid] = {"FullName": full, "Position": (pos or None)}
    return m, csv_sha

def _detect_player_array_key(sport: str) -> str:
    return "NFLPlayerGameStats" if sport == "nfl" else "CFBPlayerGameStats"

def _detect_team_array_key(sport: str) -> str:
    return "NFLTeamGameStats" if sport == "nfl" else "CFBTeamGameStats"

def process_one(sport: str, year: int, yyww: str, raw_path: str) -> str:
    """
    Process a single raw file into processed/{sport}/{year}/{yyww}.json
    Returns one of: 'processed', 'unchanged', 'error'
    """
    # Compute current raw hash and load players map/hash
    raw_sha = _sha256_file(raw_path)
    players_map, players_sha = _load_players_map()

    # Paths
    proc_dir  = os.path.join(settings.DATA_ROOT, "processed", sport, str(year))
    proc_path = os.path.join(proc_dir, f"{yyww}.json")
    meta_path = os.path.join(proc_dir, f"{yyww}.meta.json")
    _ensure_dir(proc_dir)

    # Check meta to skip if nothing changed AND processed file exists
    if os.path.isfile(meta_path) and os.path.isfile(proc_path):
        try:
            meta = json.load(open(meta_path, "r", encoding="utf-8"))
        except Exception:
            meta = {}
        if (meta.get("source_sha256") == raw_sha
            and meta.get("players_sha256") == players_sha):
            # up to date
            return "unchanged"

    # Load raw
    try:
        raw = json.load(open(raw_path, "r", encoding="utf-8"))
    except Exception:
        return "error"

    # Prune to sport-specific arrays
    team_key   = _detect_team_array_key(sport)
    player_key = _detect_player_array_key(sport)
    out = {
        team_key:   raw.get(team_key,   []) or [],
        player_key: raw.get(player_key, []) or [],
        "_computed": {}
    }

    # Enrich players
    if out[player_key]:
        # Try to detect ID key (most cases 'ID')
        sample = out[player_key][0] if isinstance(out[player_key][0], dict) else {}
        id_key = "ID"
        if id_key not in sample:
            # fallback try common variants
            for k in sample.keys():
                if str(k).lower().endswith("id") and "team" not in str(k).lower():
                    id_key = k; break

        matched = 0
        for row in out[player_key]:
            pid = str(row.get(id_key)) if row.get(id_key) is not None else None
            if pid and pid in players_map:
                row["FullName"] = players_map[pid]["FullName"]
                row["Position"] = players_map[pid]["Position"]
                matched += 1
            else:
                row.setdefault("FullName", None)
                row.setdefault("Position", None)

    # Write processed
    try:
        with open(proc_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"), indent=2)
    except Exception:
        return "error"

    # Write meta
    meta = {
        "source_sha256": raw_sha,
        "players_sha256": players_sha,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "source": os.path.relpath(raw_path, settings.DATA_ROOT).replace("\\", "/"),
    }
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, separators=(",", ":"), indent=2)
    except Exception:
        # not fatal
        pass

    return "processed"