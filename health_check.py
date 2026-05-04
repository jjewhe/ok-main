import pathlib, re, ast

print("=" * 55)
print("OMEGA ELITE - FULL HEALTH CHECK")
print("=" * 55)

# 1. Syntax check all Python files
print("\n[1] Python Syntax Check")
errors = []
for f in sorted(pathlib.Path('.').rglob('*.py')):
    if any(x in str(f) for x in ['__pycache__', '.venv', 'venv', 'build', 'audit', 'check_']):
        continue
    try:
        ast.parse(f.read_text(encoding='utf-8', errors='replace'))
        print(f"  OK: {f}")
    except SyntaxError as e:
        errors.append(f"{f}:{e.lineno}: {e.msg}")
        print(f"  FAIL: {f}:{e.lineno}: {e.msg}")

# 2. Critical import check in omega_core.py
print("\n[2] omega_core.py Critical Imports")
core = pathlib.Path('omega_core.py').read_text(encoding='utf-8', errors='replace')
for mod in ['sys','os','time','asyncio','threading','subprocess','struct',
            'socket','json','ctypes','ssl','traceback','platform',
            'urllib','string','datetime','websockets']:
    found = f'import {mod}' in core or f'from {mod}' in core
    print(f"  {'OK' if found else 'MISSING'}: {mod}")

# 3. Key function signatures in omega_core.py
print("\n[3] omega_core.py Key Function Signatures")
for sig in ['async def send(ws, obj)', 'async def send_bin(ws, tag, data)',
            'async def main()', 'def _ws_url(', 'def _generate_dga_domains(',
            'class NetScanner', 'def _init_crypto(', 'def _encrypt(',
            'def _decrypt(', 'class OmegaStealer']:
    found = sig in core
    print(f"  {'OK' if found else 'MISSING'}: {sig}")

# 4. Command coverage
print("\n[4] Command Coverage (UI vs Agent)")
html = pathlib.Path('index.html').read_text(encoding='utf-8', errors='replace')
js   = pathlib.Path('static/script.js').read_text(encoding='utf-8', errors='replace')
ext  = pathlib.Path('modules/extended_commands.py').read_text(encoding='utf-8', errors='replace') if pathlib.Path('modules/extended_commands.py').exists() else ''
ui_cmds    = set(re.findall(r"sendCmd\('([^']+)'", html + js))
agent_cmds = set(re.findall(r'register_command\(["\'](.+?)["\']\)', core))
ext_cmds   = set(re.findall(r'COMMANDS\["(.+?)"\]', ext))
all_cmds   = agent_cmds | ext_cmds
missing    = ui_cmds - all_cmds
for c in sorted(missing): print(f"  MISSING: {c}")
if not missing: print(f"  All {len(ui_cmds)} UI commands are registered!")
print(f"  Total agent commands: {len(all_cmds)} (core: {len(agent_cmds)}, ext: {len(ext_cmds)})")

# 5. web_server.py API routes
print("\n[5] Critical API Routes")
server = pathlib.Path('web_server.py').read_text(encoding='utf-8', errors='replace')
routes = ['/ws', '/api/nodes', '/api/node/command', '/api/node/socks',
          '/api/upload', '/api/stats', '/api/audit', '/api/users']
for r in routes:
    found = r in server
    print(f"  {'OK' if found else 'MISSING'}: {r}")

# 6. core/ module check
print("\n[6] core/ Modules")
for mod in ['broker.py', 'crypto.py', 'stealer.py', 'socks.py', 'database.py']:
    p = pathlib.Path('core') / mod
    print(f"  {'OK' if p.exists() else 'MISSING'}: core/{mod}")

print("\n" + "=" * 55)
print("HEALTH CHECK COMPLETE")
print("=" * 55)
