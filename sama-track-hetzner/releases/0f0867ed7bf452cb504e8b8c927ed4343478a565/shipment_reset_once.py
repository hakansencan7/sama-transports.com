import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
import accounting_db_patch as accounting_patch

app = accounting_patch.app
core = accounting_patch.core

RESET_KEY = "sevkiyat_reset_20260903_v1"
DATA_DIR = Path(core.VOLUME_DIR)
SOURCE_DB = Path(core.DB)
BACKUP_DIR = DATA_DIR / "backups"
MARKER = DATA_DIR / f".{RESET_KEY}.done"

# Operational/history tables to clear for a clean shipment start.
# Login/users, drivers, vehicles, customers, areas, cargo categories and route/fleet
# master definitions are deliberately preserved so the site remains usable.
RESET_TABLES = [
    "fuel_purchases",
    "trips",
    "audit_log",
    "vehicle_operations",
    "maintenance",
    "trip_entry_expense_labels",
    "entry_expense_memory",
    # Accounting has already been copied to /data/muhasebe.db by the earlier
    # startup hook. Remove the old duplicate accounting rows from sevkiyat.db.
    "cash_advance_settlements",
    "cash_advances",
    "cash_daily_expenses",
    "cash_daily_counts",
]


def _table_exists(c, name: str) -> bool:
    return c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _backup_sqlite(src: Path, dst: Path):
    # SQLite backup API gives a consistent backup even if WAL mode is active.
    source = sqlite3.connect(src)
    target = sqlite3.connect(dst)
    try:
        source.backup(target)
        target.commit()
    finally:
        target.close()
        source.close()


def _reset_once():
    if MARKER.exists():
        print(f"[SAMA] Shipment reset already completed: {MARKER}")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"sevkiyat_before_reset_{stamp}.db"

    if not SOURCE_DB.exists():
        raise RuntimeError(f"Shipment DB not found: {SOURCE_DB}")

    _backup_sqlite(SOURCE_DB, backup_path)
    print(f"[SAMA] Shipment DB backup created: {backup_path}")

    c = sqlite3.connect(SOURCE_DB)
    try:
        c.execute("PRAGMA foreign_keys=OFF")
        before = {}
        for table in RESET_TABLES:
            if _table_exists(c, table):
                before[table] = int(c.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])

        c.execute("BEGIN IMMEDIATE")
        try:
            for table in RESET_TABLES:
                if _table_exists(c, table):
                    c.execute(f'DELETE FROM "{table}"')
                    # Reset AUTOINCREMENT counters where applicable.
                    if _table_exists(c, "sqlite_sequence"):
                        c.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
            c.commit()
        except Exception:
            c.rollback()
            raise

        after = {}
        for table in RESET_TABLES:
            if _table_exists(c, table):
                after[table] = int(c.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        c.close()

    MARKER.write_text(
        f"reset={RESET_KEY}\nbackup={backup_path}\ncompleted_at={datetime.now().isoformat()}\nbefore={before}\nafter={after}\n",
        encoding="utf-8",
    )
    print(f"[SAMA] Shipment DB operational data reset complete. Backup: {backup_path}")
    print(f"[SAMA] Reset counts before: {before}")
    print(f"[SAMA] Reset counts after: {after}")


@app.on_event("startup")
def _shipment_reset_startup():
    # accounting_db_patch startup runs first, so accounting history has already
    # been migrated before we remove its duplicate rows from sevkiyat.db.
    _reset_once()
