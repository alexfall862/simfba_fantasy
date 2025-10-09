# app/startup.py
import os, shutil

def seed_reference_files(data_root: str, base_dir: str):
    """
    Copy reference CSVs from repo into the persistent DATA_ROOT if missing.
    base_dir is typically os.path.dirname(__file__)
    """
    src_players = os.path.join(base_dir, "assets", "players", "playerdetails.csv")
    dst_players = os.path.join(data_root, "players", "playerdetails.csv")

    src_nfl = os.path.join(base_dir, "assets", "teams", "nflteamids.csv")
    dst_nfl = os.path.join(data_root, "teams", "nflteamids.csv")

    src_cfb = os.path.join(base_dir, "assets", "teams", "cfbteamids.csv")
    dst_cfb = os.path.join(data_root, "teams", "cfbteamids.csv")

    for src, dst in [(src_players, dst_players), (src_nfl, dst_nfl), (src_cfb, dst_cfb)]:
        if os.path.isfile(src) and not os.path.isfile(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
