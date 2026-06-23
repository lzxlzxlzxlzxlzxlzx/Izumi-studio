"""Reset repo to public-safe state: empty cards, no private uploads/worldbooks."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _rm_glob(directory: Path, pattern: str) -> None:
    if not directory.exists():
        return
    for p in directory.glob(pattern):
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass


def main() -> None:
    db = DATA / "izumi.db"
    if db.exists():
        db.unlink()

    _rm_glob(DATA / "cards", "*.json")
    _rm_glob(DATA / "uploads", "*")
    _rm_glob(DATA / "worldbooks", "*.json")
    _rm_glob(DATA / "logs", "*")

    local_cfg = DATA / "local_config.json"
    # keep local_config.json — per-machine API keys, gitignored

    # Re-init empty database (only _konata_system system card)
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app.db.schema import init_db

    init_db()
    print("Public data reset complete: empty card gallery, fresh izumi.db")


if __name__ == "__main__":
    main()
