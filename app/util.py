# util.py
import os, hashlib

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def write_if_changed(json_path: str, payload: bytes) -> tuple[str, str]:
    """
    Writes payload to json_path iff content hash differs.
    Stores a sidecar {json_path}.sha with the hex digest.
    Returns (status, hash) where status in {"new","updated","unchanged","error"}.
    """
    try:
        ensure_dir(os.path.dirname(json_path))
        new_hash = sha256_bytes(payload)
        sha_path = json_path + ".sha"

        old_hash = None
        if os.path.isfile(sha_path):
            with open(sha_path, "r", encoding="utf-8") as f:
                old_hash = f.read().strip()
        elif os.path.isfile(json_path):
            # Fallback hash from file
            with open(json_path, "rb") as f:
                old_hash = sha256_bytes(f.read())

        if old_hash and old_hash == new_hash:
            return "unchanged", new_hash

        with open(json_path, "wb") as f:
            f.write(payload)
        with open(sha_path, "w", encoding="utf-8") as f:
            f.write(new_hash)

        return ("updated" if old_hash else "new"), new_hash
    except Exception:
        return "error", ""
