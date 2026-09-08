import re
import sqlite3
from pathlib import Path
import layout_patch as layout

# Keep the existing application/login/shipment database untouched.
patched = layout.patched
core = patched.core
app = layout.app

ACCOUNTING_DB = Path(core.VOLUME_DIR) / "muhasebe.db"

# Existing accounting tables are copied once from sevkiyat.db and then all
# runtime SQL for these table names is transparently redirected to muhasebe.db.
ACCOUNTING_TABLES = {
    "cash_advances": "acct_cash_advances",
    "cash_advance_settlements": "acct_cash_advance_settlements",
    "cash_daily_expenses": "acct_cash_daily_expenses",
    "cash_daily_counts": "acct_cash_daily_counts",
}

_ORIGINAL_DB = core.db


def _q(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _column_def(row) -> str:
    # PRAGMA table_info: cid,name,type,notnull,dflt_value,pk
    out = [_q(row[1]), str(row[2] or "")]
    if int(row[3] or 0):
        out.append("NOT NULL")
    if row[4] is not None:
        out.append("DEFAULT " + str(row[4]))
    return " ".join(x for x in out if x)


def _destination_create_sql(source_sql: str, source: str, dest: str) -> str:
    # Preserve the exact source schema (including PRIMARY KEY/AUTOINCREMENT and
    # columns added by earlier patches) while only changing the table name.
    pattern = re.compile(
        r"^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[`\"\[]?" + re.escape(source) + r"[`\"\]]?)",
        re.IGNORECASE,
    )
    return pattern.sub("CREATE TABLE IF NOT EXISTS " + _q(dest), source_sql, count=1)


def _migrate_existing_accounting_data():
    ACCOUNTING_DB.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(core.DB)
    dst = sqlite3.connect(ACCOUNTING_DB)
    try:
        dst.execute("PRAGMA journal_mode=WAL")
        dst.execute("PRAGMA busy_timeout=5000")
        dst.execute("""CREATE TABLE IF NOT EXISTS accounting_migration_log(
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT '',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

        for source, target in ACCOUNTING_TABLES.items():
            meta = src.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (source,),
            ).fetchone()
            if not meta or not meta[0]:
                # If this feature has never been used, its table will be created
                # directly in muhasebe.db later by the application's _ensure_* code.
                continue

            dst.execute(_destination_create_sql(meta[0], source, target))

            # Keep destination schema compatible if the old table gained columns
            # through a later migration (document_date, edit metadata, etc.).
            source_info = src.execute(f"PRAGMA table_info({_q(source)})").fetchall()
            target_info = dst.execute(f"PRAGMA table_info({_q(target)})").fetchall()
            target_cols = {r[1] for r in target_info}
            for col in source_info:
                if col[1] not in target_cols:
                    dst.execute(
                        f"ALTER TABLE {_q(target)} ADD COLUMN {_column_def(col)}"
                    )

            cols = [r[1] for r in source_info]
            if not cols:
                continue
            col_sql = ",".join(_q(c) for c in cols)
            placeholders = ",".join("?" for _ in cols)
            rows = src.execute(f"SELECT {col_sql} FROM {_q(source)}").fetchall()
            if rows:
                # Never overwrite a record already living in muhasebe.db. This
                # makes repeated deployments safe and preserves later edits.
                dst.executemany(
                    f"INSERT OR IGNORE INTO {_q(target)} ({col_sql}) VALUES ({placeholders})",
                    rows,
                )
            dst.execute(
                "INSERT INTO accounting_migration_log(key,value,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP",
                ("migrated:" + source, str(len(rows))),
            )
        dst.commit()
    finally:
        src.close()
        dst.close()


def _rewrite_sql(sql: str) -> str:
    text = str(sql)

    # PRAGMA table_info(table) needs a different qualified syntax from ordinary SQL.
    for source, target in ACCOUNTING_TABLES.items():
        text = re.sub(
            r"PRAGMA\s+table_info\s*\(\s*[`\"\[]?" + re.escape(source) + r"[`\"\]]?\s*\)",
            "PRAGMA accounting.table_info(" + _q(target) + ")",
            text,
            flags=re.IGNORECASE,
        )

    # All ordinary references become direct operations on the attached accounting DB.
    for source, target in ACCOUNTING_TABLES.items():
        text = re.sub(
            r"(?<![A-Za-z0-9_])(?:[`\"\[]?)" + re.escape(source) + r"(?:[`\"\]]?)(?![A-Za-z0-9_])",
            "accounting." + _q(target),
            text,
            flags=re.IGNORECASE,
        )
    return text


class AccountingCursor(sqlite3.Cursor):
    def execute(self, sql, parameters=()):
        return super().execute(_rewrite_sql(sql), parameters)

    def executemany(self, sql, seq_of_parameters):
        return super().executemany(_rewrite_sql(sql), seq_of_parameters)

    def executescript(self, sql_script):
        return super().executescript(_rewrite_sql(sql_script))


class AccountingConnection(sqlite3.Connection):
    def cursor(self, factory=None):
        return super().cursor(factory or AccountingCursor)

    def execute(self, sql, parameters=()):
        return super().execute(_rewrite_sql(sql), parameters)

    def executemany(self, sql, seq_of_parameters):
        return super().executemany(_rewrite_sql(sql), seq_of_parameters)

    def executescript(self, sql_script):
        return super().executescript(_rewrite_sql(sql_script))


def accounting_aware_db():
    c = sqlite3.connect(core.DB, factory=AccountingConnection)
    c.row_factory = sqlite3.Row
    # Bypass our SQL rewriting while attaching the second file.
    sqlite3.Connection.execute(c, "ATTACH DATABASE ? AS accounting", (str(ACCOUNTING_DB),))
    sqlite3.Connection.execute(c, "PRAGMA accounting.busy_timeout=5000")
    return c


@app.on_event("startup")
def _start_accounting_database():
    # app.py's own startup handler is registered first and initializes sevkiyat.db.
    # Only after that do we copy historical cash/advance data and redirect future use.
    _migrate_existing_accounting_data()
    core.db = accounting_aware_db
    print(f"[SAMA] Accounting database active: {ACCOUNTING_DB}")

# Expose the same names expected by the next patch in the chain.
app = layout.app
