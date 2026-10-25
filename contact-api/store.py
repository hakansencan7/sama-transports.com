"""Small, process-safe abuse limiter and submission ledger; no message storage."""
import sqlite3
import time


class Limited(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (bucket TEXT, created INTEGER);
                CREATE INDEX IF NOT EXISTS events_lookup ON events(bucket, created);
                CREATE TABLE IF NOT EXISTS submissions (
                    id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL, created INTEGER NOT NULL
                );
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    @staticmethod
    def _limits(db, limits, now):
        for bucket, count, window in limits:
            used = db.execute("SELECT count(*) FROM events WHERE bucket=? AND created>?",
                              (bucket, now - window)).fetchone()[0]
            if used >= count:
                raise Limited()
        for bucket in {entry[0] for entry in limits}:
            db.execute("INSERT INTO events VALUES (?,?)", (bucket, now))

    @staticmethod
    def _clean(db, now):
        db.execute("DELETE FROM events WHERE created<?", (now - 86400,))
        db.execute("DELETE FROM submissions WHERE created<?", (now - 172800,))

    def limit(self, limits):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = int(time.time())
            self._clean(db, now)
            self._limits(db, limits, now)

    def claim(self, request_id, fingerprint, client):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = int(time.time())
            self._clean(db, now)
            row = db.execute("SELECT fingerprint,status FROM submissions WHERE id=?",
                             (request_id,)).fetchone()
            if row:
                if row[0] != fingerprint and row[1] != "retryable":
                    return "changed"
                if row[1] != "retryable":
                    return row[1]
            self._limits(db, [("send:" + client, 3, 600),
                              ("send:" + client, 10, 86400),
                              ("send:global", 60, 3600)], now)
            db.execute("INSERT OR REPLACE INTO submissions VALUES (?,?,?,?)",
                       (request_id, fingerprint, "pending", now))
        return "claimed"

    def finish(self, request_id, status):
        with self.connect() as db:
            db.execute("UPDATE submissions SET status=? WHERE id=?", (status, request_id))
