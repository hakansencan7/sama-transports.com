import sqlite3
from pathlib import Path
import accounting_db_patch as accounting

app = accounting.app
core = accounting.core

DATA_DIR = Path(core.VOLUME_DIR)
BACKUP_DIR = DATA_DIR / "backups"
MARKER = DATA_DIR / ".plate_master_restored_from_backup_v1.done"


def _restore_plate_master():
    if MARKER.exists():
        print(f"[SAMA] Plate master restore already completed: {MARKER}")
        return

    backups = sorted(BACKUP_DIR.glob("sevkiyat_before_reset_*.db"), reverse=True)
    if not backups:
        print("[SAMA] Plate master restore skipped: shipment backup not found")
        return

    backup = backups[0]
    src = sqlite3.connect(backup)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(core.DB)
    dst.row_factory = sqlite3.Row
    try:
        plates = []
        seen = set()

        # First prefer the old fleet master if it existed in the backup.
        try:
            for r in src.execute("SELECT plate FROM fleet_vehicles WHERE TRIM(COALESCE(plate,''))<>''"):
                p = str(r['plate'] or '').strip().upper()
                if p and p not in seen:
                    seen.add(p); plates.append(p)
        except Exception:
            pass

        # Then recover every plate that ever appeared in shipment history.
        try:
            for r in src.execute("SELECT DISTINCT plate FROM trips WHERE TRIM(COALESCE(plate,''))<>''"):
                p = str(r['plate'] or '').strip().upper()
                if p and p not in seen:
                    seen.add(p); plates.append(p)
        except Exception:
            pass

        # Legacy vehicles table may contain additional manually maintained plates.
        try:
            for r in src.execute("SELECT plate FROM vehicles WHERE TRIM(COALESCE(plate,''))<>''"):
                p = str(r['plate'] or '').strip().upper()
                if p and p not in seen:
                    seen.add(p); plates.append(p)
        except Exception:
            pass

        added_fleet = 0
        added_legacy = 0
        for p in plates:
            try:
                before = dst.total_changes
                dst.execute("INSERT OR IGNORE INTO fleet_vehicles(plate,is_active) VALUES(?,1)", (p,))
                if dst.total_changes > before:
                    added_fleet += 1
            except Exception:
                pass
            try:
                before = dst.total_changes
                dst.execute("INSERT OR IGNORE INTO vehicles(plate,active) VALUES(?,1)", (p,))
                if dst.total_changes > before:
                    added_legacy += 1
            except Exception:
                pass

        dst.commit()
        MARKER.write_text(
            f"backup={backup}\nplates_found={len(plates)}\nadded_fleet={added_fleet}\nadded_legacy={added_legacy}\n",
            encoding="utf-8",
        )
        print(f"[SAMA] Plate master restored from backup: {backup}")
        print(f"[SAMA] Plate master counts: found={len(plates)} added_fleet={added_fleet} added_legacy={added_legacy}")
    finally:
        dst.close()
        src.close()


@app.on_event("startup")
def _plate_master_restore_startup():
    _restore_plate_master()
