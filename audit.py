import pathlib, re

# --- 1. Find all sendCmd calls in index.html + script.js ---
html = pathlib.Path('index.html').read_text(encoding='utf-8', errors='replace')
js   = pathlib.Path('static/script.js').read_text(encoding='utf-8', errors='replace')

ui_cmds = set(re.findall(r"sendCmd\('([^']+)'", html + js))

# --- 2. Find all @register_command in omega_core.py ---
core = pathlib.Path('omega_core.py').read_text(encoding='utf-8', errors='replace')
agent_cmds = set(re.findall(r'register_command\(["\'](.+?)["\']\)', core))

# --- 3. Find all API routes in web_server.py ---
server = pathlib.Path('web_server.py').read_text(encoding='utf-8', errors='replace')
api_routes = set(re.findall(r'@app\.(get|post|delete|put)\(["\']([^"\']+)', server))

# --- 4. Find all JS functions referenced in HTML onclick but check if defined ---
onclick_fns = set(re.findall(r'onclick="([a-zA-Z_]+)\(', html))
js_defined  = set(re.findall(r'(?:function |window\.)([a-zA-Z_]+)\s*[=(]', js))

print('=== UI cmds missing from agent ===')
missing = ui_cmds - agent_cmds
for c in sorted(missing): print(f'  MISSING_AGENT_CMD: {c}')
if not missing: print('  All matched!')

print()
print('=== onclick handlers missing from script.js ===')
missing_fns = onclick_fns - js_defined
for f in sorted(missing_fns): print(f'  MISSING_JS_FN: {f}')
if not missing_fns: print('  All matched!')

print()
print(f'=== Summary ===')
print(f'  Agent commands: {len(agent_cmds)}')
print(f'  UI sendCmd calls: {len(ui_cmds)}')
print(f'  API routes: {len(api_routes)}')
print(f'  onclick handlers: {len(onclick_fns)}')

print()
print('=== All agent commands ===')
for c in sorted(agent_cmds): print(f'  {c}')
