# sync.py
import os, re, time, requests
from typing import Dict, List
from config import API_BASE, DATA_ROOT, SPORTS
from util import ensure_dir, write_if_changed
from processing import process_one_file

ALL_NULL_PATTERNS = {
    "nfl": [
        r'"CFBPlayerGameStats"\s*:\s*null',
        r'"CFBPlayerSeasonStats"\s*:\s*null',
        r'"CFBTeamGameStats"\s*:\s*null',
        r'"CFBTeamSeasonStats"\s*:\s*null',
        r'"NFLPlayerGameStats"\s*:\s*\[\s*\]',
        r'"NFLPlayerSeasonStats"\s*:\s*null',
        r'"NFLTeamGameStats"\s*:\s*\[\s*\]',
        r'"NFLTeamSeasonStats"\s*:\s*null',
    ],
    "cfb": [
        r'"CFBPlayerGameStats"\s*:\s*\[\s*\]',
        r'"CFBPlayerSeasonStats"\s*:\s*null',
        r'"CFBTeamGameStats"\s*:\s*\[\s*\]',
        r'"CFBTeamSeasonStats"\s*:\s*null',
        r'"NFLPlayerGameStats"\s*:\s*null',
        r'"NFLPlayerSeasonStats"\s*:\s*null',
        r'"NFLTeamGameStats"\s*:\s*null',
        r'"NFLTeamSeasonStats"\s*:\s*null',
    ]
}

def start_week_for(sport: str) -> int:
    return 1 if sport == "nfl" else 0

def is_all_null_body(sport: str, body: bytes) -> bool:
    s = body.decode("utf-8", errors="ignore")
    pats = ALL_NULL_PATTERNS["nfl" if sport=="nfl" else "cfb"]
    return all(re.search(p, s, flags=re.I) for p in pats)

def yyww(year: int, week: int) -> str:
    return f"{year%100:02d}{week:02d}"

def run_sync(*, start_year: int, years_ahead: int, max_week: int, rate_limit_ms: int) -> Dict[str, int]:
    now_year = int(time.strftime("%Y"))
    max_year = now_year + years_ahead

    stats = {"new":0, "updated":0, "unchanged":0}
    session = requests.Session()
    headers = {"Accept":"application/json"}

    for sport in SPORTS:
        for year in range(start_year, max_year + 1):
            stop_season = False
            for week in range(start_week_for(sport), max_week + 1):
                if stop_season: break

                code = yyww(year, week)
                url = f"{API_BASE}/{sport}/{year}/{code}/WEEK/2"
                raw_path = os.path.join(DATA_ROOT, sport, str(year), f"{code}.json")
                ensure_dir(os.path.dirname(raw_path))

                r = session.get(url, headers=headers, timeout=30)
                if r.status_code != 200:
                    continue

                body = r.content
                if len(body) > 1_500_000 and is_all_null_body(sport, body):
                    # early stop if it's the "all-null" sentinel
                    stop_season = True
                    break

                status, new_hash = write_if_changed(raw_path, body)
                if status == "new":
                    stats["new"] += 1
                elif status == "updated":
                    stats["updated"] += 1
                elif status == "unchanged":
                    stats["unchanged"] += 1

                # Always try to (re)process; it will just overwrite processed output
                process_one_file(sport, year, code, raw_path, DATA_ROOT)

                time.sleep(rate_limit_ms / 1000.0)

    return stats
