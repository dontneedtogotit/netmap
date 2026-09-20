/**
 * app.js - NetMap UI Controller, Topology Graph Renderer, Multi-Agent Studio,
 * Device Customization Store, Network Suggestions Engine & AI Documentation System.
 */

let state = {
  topology: null,
  isScanning: false,
  selectedDevice: null,
  activeTab: 'topology',
  highlightedIps: [],
  deviceFilter: 'all',
  deviceSearch: '',
  suggestionFilter: 'all',
  activeDocId: null,
  docs: [],
  devicePresets: {
    roles: [],
    locations: [],
    priorities: [],
    segments: []
  },
  models: {
    mistral: [],
    openrouter: [],
    gemini: []
  },
  config: {
    ai_provider: 'mistral',
    mistral_has_key: false,
    mistral_raw_key: '',
    mistral_model: 'mistral-small-latest',
    openrouter_has_key: false,
    openrouter_raw_key: '',
    openrouter_model: 'deepseek/deepseek-v4-flash-0731:free',
    gemini_has_key: false,
    gemini_raw_key: '',
    gemini_model: 'gemini-2.0-flash'
  },
  agentChatSessionId: null,
  profiles: [],
  activeProfileId: null,
  viewingProfileId: null,
  topoZoom: {
    scale: 1,
    panX: 0,
    panY: 0,
    isPanning: false,
    startX: 0,
    startY: 0
  },
  lastUpdatedAt: null,
  freshness: {
    network_metrics: null,
    wan_info: null,
    devices: null
  }
};

const ICONS = {
  internet: '🌐',
  modem: '📦',
  router: '📡',
  extender: '📶',
  host: '💻',
  camera: '📹',
  nvr: '📼',
  smart_tv: '📺',
  pc: '🖥️',
  mobile: '📱',
  nas: '💾',
  iot: '🔌',
  network_device: '🖧',
  unknown: '⚙️'
};

// Document Ready
document.addEventListener('DOMContentLoaded', () => {
  initNav();
  initProfiles();
  initRouterAudit();
  initAgentStudio();
  initDiagnostics();
  initInspector();
  initSettings();
  initDeviceToolbar();
  initSuggestionsFilter();
  initDocumentation();
  initTopologyControls();
  loadInitialData();
});

// -------------------------------------------------------------
// Toast Notification Utility
// -------------------------------------------------------------
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  let icon = 'ℹ️';
  if (type === 'success') icon = '✓';
  if (type === 'warning') icon = '⚠️';
  if (type === 'error') icon = '✕';

  toast.innerHTML = `
    <span class="toast-icon">${icon}</span>
    <span class="toast-msg">${message}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => toast.classList.add('show'), 10);

  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// -------------------------------------------------------------
// Navigation Tabs
// -------------------------------------------------------------
function initNav() {
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      tab.classList.add('active');
      const target = tab.getAttribute('data-tab');
      state.activeTab = target;
      const el = document.getElementById(`tab-${target}`);
      if (el) el.classList.add('active');

      if (target === 'topology' && state.topology) {
        renderTopology(state.topology);
      } else if (target === 'suggestions' && state.topology) {
        renderSuggestions(state.topology.suggestions || []);
      } else if (target === 'docs') {
        loadDocumentationIndex();
      } else if (target === 'router-settings' && state.topology) {
        renderRouterSettings(state.topology.router_settings);
      }
    });
  });

  document.getElementById('btn-rescan').addEventListener('click', triggerRescan);
}

// -------------------------------------------------------------
// Initial Data Fetch
// -------------------------------------------------------------
async function loadInitialData() {
  updateStatus("Scanning active network topology, device profiles and suggestions...");
  try {
    // 1. Fetch Config
    const cfgRes = await fetch('/api/config');
    state.config = await cfgRes.json();
    updateEngineBadge();

    // 2. Fetch Models
    try {
      const modRes = await fetch('/api/models');
      state.models = await modRes.json();
    } catch (e) {}

    // 3. Fetch Device Presets & Settings
    try {
      const devRes = await fetch('/api/devices/settings');
      const devData = await devRes.json();
      state.devicePresets = devData.presets || {};
    } catch (e) {}

    // 4. Fetch Status & Topology
    const res = await fetch('/api/status');
    const data = await res.json();
    state.activeProfileId = data.active_profile_id;
    state.viewingProfileId = data.viewing_profile_id || data.active_profileId;
    state.topology = data.topology;
    state.lastUpdatedAt = new Date();
    state.freshness = data.freshness || state.freshness;
    updateUIWithTopology(state.topology);
    updateFreshnessUI();
    await refreshProfilesList();
    await fetchRouterAuditStatus();

    if (!state.topology && !state.isScanning) {
      triggerRescan();
    }
  } catch (err) {
    console.error("Failed to load initial data:", err);
    updateStatus("Error connecting to NetMap engine");
    showToast("Error connecting to NetMap local engine", "error");
  }
}

function updateEngineBadge() {
  const badge = document.getElementById('val-ai');
  const label = document.getElementById('active-engine-label');
  const advBadge = document.getElementById('advisor-badge');

  const provider = state.config.ai_provider || 'local';

  if (provider === 'gemini' && state.config.gemini_has_key) {
    badge.textContent = `Gemini (${state.config.gemini_model || '2.0-flash'})`;
    label.textContent = `Engine: Google Gemini (${state.config.gemini_model || 'gemini-2.0-flash'})`;
    advBadge.textContent = "Gemini Agents";
    advBadge.style.background = "rgba(74, 222, 128, 0.2)";
    advBadge.style.color = "var(--accent-green)";
  } else if (provider === 'mistral' && state.config.mistral_has_key) {
    badge.textContent = `Mistral (${state.config.mistral_model.replace('-latest', '')})`;
    label.textContent = `Engine: Mistral AI (${state.config.mistral_model})`;
    advBadge.textContent = "Mistral Agents";
    advBadge.style.background = "rgba(247, 118, 142, 0.2)";
    advBadge.style.color = "var(--accent-red)";
  } else if (provider === 'openrouter' && state.config.openrouter_has_key) {
    const shortModel = state.config.openrouter_model.split('/')[1] || state.config.openrouter_model;
    badge.textContent = shortModel.replace(':free', '');
    label.textContent = `Engine: OpenRouter (${shortModel})`;
    advBadge.textContent = "AI Agents Live";
    advBadge.style.background = "rgba(187, 154, 247, 0.2)";
    advBadge.style.color = "var(--accent-purple)";
  } else {
    badge.textContent = "Local Agents";
    label.textContent = "Engine: Local Multi-Agent Expert (Deterministic Tools)";
    advBadge.textContent = "Local Agents";
    advBadge.style.background = "rgba(125, 207, 255, 0.2)";
    advBadge.style.color = "var(--accent-cyan)";
  }
}

// -------------------------------------------------------------
// Navigation Tabs & Keyboard Shortcuts
// -------------------------------------------------------------
function initNav() {
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      tab.classList.add('active');
      const target = tab.getAttribute('data-tab');
      state.activeTab = target;
      const el = document.getElementById(`tab-${target}`);
      if (el) el.classList.add('active');

      if (target === 'topology' && state.topology) {
        renderTopology(state.topology);
      } else if (target === 'suggestions' && state.topology) {
        renderSuggestions(state.topology.suggestions || []);
      } else if (target === 'docs') {
        loadDocumentationIndex();
      } else if (target === 'router-settings' && state.topology) {
        renderRouterSettings(state.topology.router_settings);
      } else if (target === 'devices' && state.topology) {
        renderDeviceTable(state.topology.devices || []);
      }
    });
  });

  document.getElementById('btn-rescan')?.addEventListener('click', triggerRescan);

  // Status pills quick navigation
  document.getElementById('pill-router')?.addEventListener('click', () => {
    document.querySelector('.nav-tab[data-tab="router-settings"]')?.click();
  });
  document.getElementById('pill-isp')?.addEventListener('click', () => {
    document.querySelector('.nav-tab[data-tab="diagnostics"]')?.click();
  });
  document.getElementById('pill-cgnat')?.addEventListener('click', () => {
    document.querySelector('.nav-tab[data-tab="diagnostics"]')?.click();
  });
  document.getElementById('pill-ai')?.addEventListener('click', () => {
    document.getElementById('modal-settings')?.classList.add('active');
  });

  // Global Keyboard Shortcuts
  window.addEventListener('keydown', (e) => {
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
      if (e.key === 'Escape') {
        document.activeElement.blur();
        closeInspector();
        document.getElementById('modal-settings')?.classList.remove('active');
        document.getElementById('profiles-modal')?.classList.remove('active');
        const hud = document.getElementById('topo-hud');
        if (hud) hud.style.display = 'none';
        currentHoveredNodeId = null;
      }
      return;
    }

    if (e.key >= '1' && e.key <= '7') {
      const tabNames = ['topology', 'suggestions', 'solver', 'docs', 'router-settings', 'devices', 'diagnostics'];
      const targetTab = tabNames[parseInt(e.key) - 1];
      if (targetTab) {
        const tabBtn = document.querySelector(`.nav-tab[data-tab="${targetTab}"]`);
        tabBtn?.click();
      }
    } else if (e.key === '/' || e.key === 's') {
      e.preventDefault();
      const tabBtn = document.querySelector('.nav-tab[data-tab="devices"]');
      tabBtn?.click();
      setTimeout(() => {
        const searchInput = document.getElementById('device-search-input');
        searchInput?.focus();
        searchInput?.select();
      }, 50);
    } else if (e.key === 'r' || e.key === 'R') {
      triggerRescan();
    } else if (e.key === 'Escape') {
      closeInspector();
      document.getElementById('modal-settings')?.classList.remove('active');
      document.getElementById('profiles-modal')?.classList.remove('active');
      const hud = document.getElementById('topo-hud');
      if (hud) hud.style.display = 'none';
      currentHoveredNodeId = null;
    }
  });
}

// -------------------------------------------------------------
// Rescan Subnet & Fingerprint Devices
// -------------------------------------------------------------
async function triggerRescan() {
  if (state.isScanning) return;
  state.isScanning = true;
  const btn = document.getElementById('btn-rescan');
  const text = document.getElementById('rescan-text');
  const icon = btn?.querySelector('svg');
  if (btn) btn.disabled = true;
  if (icon) icon.classList.add('spinning');
  if (text) text.textContent = "Scanning Subnet...";
  updateStatus("Scanning subnet, fingerprinting cameras/NVRs, and evaluating network suggestions...");
  showToast("Network scan started in background", "info");

  try {
    await fetch('/api/scan', { method: 'POST' });
    const startedAt = Date.now();
    const maxMs = 5 * 60 * 1000;
    const checkInterval = setInterval(async () => {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        if (!data.scanning) {
          clearInterval(checkInterval);
          state.isScanning = false;
          if (btn) btn.disabled = false;
          if (icon) icon.classList.remove('spinning');
          if (text) text.textContent = "Rescan Network";
          state.topology = data.topology;
          updateUIWithTopology(state.topology);
          showToast("Network scan completed successfully", "success");
        } else if (Date.now() - startedAt > maxMs) {
          clearInterval(checkInterval);
          state.isScanning = false;
          if (btn) btn.disabled = false;
          if (icon) icon.classList.remove('spinning');
          if (text) text.textContent = "Rescan Network";
          updateStatus("Scan timed out; showing last known results.");
          showToast("Scan is taking longer than expected. Showing current data.", "warning");
        }
      } catch (pollErr) {
        console.error("Scan status poll failed:", pollErr);
        if (Date.now() - startedAt > maxMs) {
          clearInterval(checkInterval);
          state.isScanning = false;
          if (btn) btn.disabled = false;
          if (icon) icon.classList.remove('spinning');
          if (text) text.textContent = "Rescan Network";
          updateStatus("Scan connection lost; showing last known results.");
          showToast("Lost connection to NetMap during scan.", "error");
        }
      }
    }, 1500);
  } catch (err) {
    console.error("Rescan failed:", err);
    state.isScanning = false;
    if (btn) btn.disabled = false;
    if (icon) icon.classList.remove('spinning');
    if (text) text.textContent = "Rescan Network";
    showToast("Rescan failed", "error");
  }
}

function updateStatus(msg) {
  const el = document.getElementById('connection-status');
  if (el) el.textContent = msg;
}

function updateFreshnessUI() {
  const el = document.getElementById('freshness-label');
  if (!el) return;
  const f = state.freshness || {};
  const parts = [];
  if (f.network_metrics?.is_fresh) parts.push('metrics fresh');
  else if (f.network_metrics?.is_stale) parts.push('metrics stale');
  if (f.wan_info?.is_fresh) parts.push('wan fresh');
  else if (f.wan_info?.is_stale) parts.push('wan stale');
  if (f.devices?.is_fresh) parts.push('devices fresh');
  else if (f.devices?.is_stale) parts.push('devices stale');
  const label = parts.length ? parts.join(', ') : 'freshness unavailable';
  const ts = state.lastUpdatedAt ? state.lastUpdatedAt.toLocaleTimeString() : '';
  el.textContent = ts ? `${label} · updated ${ts}` : label;
}

// -------------------------------------------------------------
// Main UI Update
// -------------------------------------------------------------
function updateUIWithTopology(topo) {
  if (!topo) return;

  const profile = topo.profile || {};
  if (profile.id) {
    state.viewingProfileId = profile.id;
    const valProfile = document.getElementById('val-profile');
    if (valProfile) valProfile.textContent = profile.name || profile.ssid || 'Default Network';
    
    const badgeProfile = document.getElementById('badge-profile-state');
    const dotProfile = document.getElementById('dot-profile');
    const isLive = !state.activeProfileId || (profile.id === state.activeProfileId);
    
    if (badgeProfile) {
      if (isLive) {
        badgeProfile.textContent = 'LIVE';
        badgeProfile.className = 'pill-badge-live';
        if (dotProfile) dotProfile.className = 'pill-dot emerald';
      } else {
        badgeProfile.textContent = 'SAVED';
        badgeProfile.className = 'pill-badge-live saved';
        if (dotProfile) dotProfile.className = 'pill-dot blue';
      }
    }

    const banner = document.getElementById('saved-profile-banner');
    const bannerName = document.getElementById('banner-profile-name');
    if (banner) {
      if (!isLive) {
        banner.style.display = 'flex';
        if (bannerName) bannerName.textContent = profile.name || profile.id;
      } else {
        banner.style.display = 'none';
      }
    }

    if (profile.is_new) {
      showToast(`Connected to new Access Point: ${profile.ssid || profile.name || 'New AP'}. Created new profile '${profile.name}'!`, 'success', 6000);
      profile.is_new = false;
    }
  }

  const router = topo.router || {};
  const wan = topo.wan || {};
  const host = topo.host || {};
  const wifi = host.wifi || {};

  document.getElementById('val-router').textContent = router.name || 'Archer BE550 v2';
  document.getElementById('val-isp').textContent = `${wan.isp || 'Aussie Broadband'} (${wan.city || 'AU'})`;
  document.getElementById('val-cgnat').textContent = wan.cgnat_active ? 'CGNAT Active' : 'Direct Public IP';
  
  const statusEl = document.getElementById('connection-status');
  let camInfo = '';
  if (topo.has_cameras || topo.has_nvrs) {
    camInfo = ' • 📹 Security Cameras / NVR Detected';
  }
  const subnetStr = profile.subnet || (host.ip ? host.ip.split('.').slice(0, 3).join('.') + '.0/24' : '192.168.0.0/24');
  statusEl.textContent = `Connected via ${host.interface || 'wlo1'} (${host.ip || '192.168.0.5'}) • Subnet ${subnetStr}${camInfo}`;

  const wifiLabel = document.getElementById('wifi-label');
  if (wifi.ssid) {
    wifiLabel.textContent = `Wi-Fi: ${wifi.ssid} (${wifi.frequency || ''} Ch ${wifi.channel || ''}, ${wifi.signal || ''})`;
  } else {
    wifiLabel.textContent = `Interface: ${host.interface || 'wlo1'} (${host.ip || ''})`;
  }

  const devs = topo.devices || [];
  document.getElementById('device-count').textContent = devs.length;

  // Suggestions Badge count
  const suggestions = topo.suggestions || [];
  const sugBadge = document.getElementById('sug-badge');
  if (sugBadge) sugBadge.textContent = suggestions.length;

  renderTopology(topo);
  renderSuggestions(suggestions);
  renderDeviceTable(devs);
  renderRouterSettings(topo.router_settings);
  renderDiagnostics(topo);
}

// -------------------------------------------------------------
// 1. TOPOLOGY GRAPH RENDERER (SVG) WITH ZOOM & PAN
// -------------------------------------------------------------
function initTopologyControls() {
  const container = document.getElementById('canvas-container');
  if (!container) return;

  document.getElementById('btn-zoom-in')?.addEventListener('click', () => {
    state.topoZoom.scale = Math.min(state.topoZoom.scale + 0.2, 2.5);
    applyTopologyTransform();
  });

  document.getElementById('btn-zoom-out')?.addEventListener('click', () => {
    state.topoZoom.scale = Math.max(state.topoZoom.scale - 0.2, 0.5);
    applyTopologyTransform();
  });

  document.getElementById('btn-zoom-reset')?.addEventListener('click', () => {
    state.topoZoom.scale = 1;
    state.topoZoom.panX = 0;
    state.topoZoom.panY = 0;
    applyTopologyTransform();
  });

  document.getElementById('btn-export-topo')?.addEventListener('click', exportTopologySvg);

  // Pan interaction
  container.addEventListener('mousedown', (e) => {
    if (e.target.closest('.topo-node')) return;
    state.topoZoom.isPanning = true;
    state.topoZoom.startX = e.clientX - state.topoZoom.panX;
    state.topoZoom.startY = e.clientY - state.topoZoom.panY;
    container.style.cursor = 'grabbing';
  });

  window.addEventListener('mousemove', (e) => {
    if (!state.topoZoom.isPanning) return;
    state.topoZoom.panX = e.clientX - state.topoZoom.startX;
    state.topoZoom.panY = e.clientY - state.topoZoom.startY;
    applyTopologyTransform();
  });

  window.addEventListener('mouseup', () => {
    state.topoZoom.isPanning = false;
    if (container) container.style.cursor = 'grab';
  });

  container.addEventListener('wheel', (e) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.1 : -0.1;
    state.topoZoom.scale = Math.min(Math.max(state.topoZoom.scale + delta, 0.5), 2.5);
    applyTopologyTransform();
  }, { passive: false });

  // Persistent HUD card listeners
  const hud = document.getElementById('topo-hud');
  if (hud) {
    hud.addEventListener('mouseenter', () => clearTimeout(hudTimeout));
    hud.addEventListener('mouseleave', scheduleHideNodeHud);
  }
}

function applyTopologyTransform() {
  const g = document.getElementById('topo-main-group');
  if (g) {
    g.setAttribute('transform', `translate(${state.topoZoom.panX}, ${state.topoZoom.panY}) scale(${state.topoZoom.scale})`);
  }
}

function exportTopologySvg() {
  const svg = document.getElementById('topo-svg');
  if (!svg) return;
  const serializer = new XMLSerializer();
  const source = serializer.serializeToString(svg);
  const blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `netmap-topology-${Date.now()}.svg`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  showToast("Topology SVG exported successfully", "success");
}

let hudTimeout = null;
let currentHoveredNodeId = null;

function getNodeIconSvg(category, r) {
  const s = r * 0.95;
  const h = s / 2;
  switch (category) {
    case 'router':
      return `
        <path d="M ${-h*0.6} ${-h*0.4} L ${-h*0.3} ${h*0.2} M ${h*0.6} ${-h*0.4} L ${h*0.3} ${h*0.2}" stroke="#7dcfff" stroke-width="2" stroke-linecap="round"/>
        <rect x="${-h*0.8}" y="${h*0.1}" width="${h*1.6}" height="${h*0.8}" rx="2" fill="#131d2e" stroke="#7dcfff" stroke-width="1.8"/>
        <circle cx="${-h*0.4}" cy="${h*0.5}" r="1.5" fill="#10b981"/>
        <circle cx="0" cy="${h*0.5}" r="1.5" fill="#7dcfff"/>
        <circle cx="${h*0.4}" cy="${h*0.5}" r="1.5" fill="#7dcfff"/>
        <path d="M ${-h*0.7} ${-h*0.7} A ${h} ${h} 0 0 1 ${h*0.7} ${-h*0.7}" fill="none" stroke="rgba(125,207,255,0.6)" stroke-width="1.5" stroke-linecap="round"/>
      `;
    case 'modem':
      return `
        <rect x="${-h*0.7}" y="${-h*0.7}" width="${h*1.4}" height="${h*1.4}" rx="3" fill="#181528" stroke="#bb9af7" stroke-width="1.8"/>
        <line x1="${-h*0.4}" y1="${-h*0.2}" x2="${h*0.4}" y2="${-h*0.2}" stroke="#bb9af7" stroke-width="1.5"/>
        <circle cx="${-h*0.35}" cy="${h*0.3}" r="1.5" fill="#10b981"/>
        <circle cx="0" cy="${h*0.3}" r="1.5" fill="#10b981"/>
        <circle cx="${h*0.35}" cy="${h*0.3}" r="1.5" fill="#7dcfff"/>
      `;
    case 'internet':
      return `
        <circle cx="0" cy="0" r="${h*0.75}" fill="none" stroke="#bb9af7" stroke-width="1.8"/>
        <ellipse cx="0" cy="0" rx="${h*0.35}" ry="${h*0.75}" fill="none" stroke="#bb9af7" stroke-width="1.2"/>
        <line x1="${-h*0.75}" y1="0" x2="${h*0.75}" y2="0" stroke="#bb9af7" stroke-width="1.2"/>
      `;
    case 'extender':
      return `
        <rect x="${-h*0.6}" y="${-h*0.3}" width="${h*1.2}" height="${h*1.0}" rx="2" fill="#141a2e" stroke="#7aa2f7" stroke-width="1.8"/>
        <path d="M ${-h*0.8} ${-h*0.6} A ${h*0.8} ${h*0.8} 0 0 1 ${h*0.8} ${-h*0.6}" fill="none" stroke="#7aa2f7" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="0" cy="${h*0.2}" r="2" fill="#10b981"/>
      `;
    case 'host':
    case 'pc':
      return `
        <rect x="${-h*0.75}" y="${-h*0.7}" width="${h*1.5}" height="${h*1.0}" rx="2" fill="#14221b" stroke="#9ece6a" stroke-width="1.8"/>
        <line x1="${-h*0.3}" y1="${h*0.3}" x2="${h*0.3}" y2="${h*0.3}" stroke="#9ece6a" stroke-width="2"/>
        <line x1="0" y1="${h*0.3}" x2="0" y2="${h*0.6}" stroke="#9ece6a" stroke-width="2"/>
        <line x1="${-h*0.4}" y1="${h*0.6}" x2="${h*0.4}" y2="${h*0.6}" stroke="#9ece6a" stroke-width="2" stroke-linecap="round"/>
        <path d="M ${-h*0.45} ${-h*0.25} L ${-h*0.2} ${-h*0.1} L ${-h*0.45} ${h*0.05}" fill="none" stroke="#9ece6a" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="${-h*0.05}" y1="${h*0.05}" x2="${h*0.35}" y2="${h*0.05}" stroke="#9ece6a" stroke-width="1.5"/>
      `;
    case 'camera':
      return `
        <path d="M ${-h*0.6} ${-h*0.4} L ${h*0.3} ${-h*0.4} L ${h*0.6} ${-h*0.6} L ${h*0.6} ${h*0.4} L ${h*0.3} ${h*0.2} L ${-h*0.6} ${h*0.2} Z" fill="#241e13" stroke="#f59e0b" stroke-width="1.8" stroke-linejoin="round"/>
        <circle cx="${-h*0.15}" cy="${-h*0.1}" r="${h*0.25}" fill="#f59e0b"/>
        <circle cx="${-h*0.15}" cy="${-h*0.1}" r="${h*0.12}" fill="#0c0e14"/>
        <line x1="${-h*0.6}" y1="${h*0.2}" x2="${-h*0.6}" y2="${h*0.6}" stroke="#f59e0b" stroke-width="2"/>
      `;
    case 'nvr':
      return `
        <rect x="${-h*0.8}" y="${-h*0.5}" width="${h*1.6}" height="${h*1.1}" rx="2" fill="#261220" stroke="#ec4899" stroke-width="1.8"/>
        <rect x="${-h*0.6}" y="${-h*0.3}" width="${h*0.5}" height="${h*0.7}" rx="1" fill="none" stroke="#ec4899" stroke-width="1.2"/>
        <rect x="0" y="${-h*0.3}" width="${h*0.5}" height="${h*0.7}" rx="1" fill="none" stroke="#ec4899" stroke-width="1.2"/>
        <circle cx="${h*0.6}" cy="${-h*0.2}" r="1.5" fill="#10b981"/>
        <circle cx="${h*0.6}" cy="${-h*0.2}" r="1.5" fill="#ec4899"/>
      `;
    case 'smart_tv':
      return `
        <rect x="${-h*0.85}" y="${-h*0.6}" width="${h*1.7}" height="${h*1.05}" rx="2" fill="#261d12" stroke="#e0af68" stroke-width="1.8"/>
        <line x1="0" y1="${h*0.45}" x2="0" y2="${h*0.7}" stroke="#e0af68" stroke-width="2"/>
        <line x1="${-h*0.4}" y1="${h*0.7}" x2="${h*0.4}" y2="${h*0.7}" stroke="#e0af68" stroke-width="2" stroke-linecap="round"/>
        <circle cx="${h*0.65}" cy="${h*0.3}" r="1.2" fill="#e0af68"/>
      `;
    default:
      return `
        <circle cx="0" cy="0" r="${h*0.6}" fill="#161e2e" stroke="#7dcfff" stroke-width="1.6"/>
        <circle cx="0" cy="0" r="${h*0.25}" fill="#7dcfff"/>
      `;
  }
}

function showNodeHud(node, event) {
  clearTimeout(hudTimeout);
  const hud = document.getElementById('topo-hud');
  if (!hud) return;

  const isSameNode = (currentHoveredNodeId === node.id);
  currentHoveredNodeId = node.id;

  if (!isSameNode) {
    const dev = node.data || {};
    const cat = dev.category || 'unknown';
    const ports = (dev.open_ports || []).map(p => {
      const isCam = [554, 8554, 8000, 37777].includes(p);
      return `<span class="port-tag ${isCam ? 'cam' : ''}">${p}</span>`;
    }).join(' ') || '<span style="color:var(--text-muted);font-size:0.7rem;">None detected</span>';
    
    const ping = dev.latency ? `${dev.latency.toFixed(1)} ms` : (dev.is_gateway ? '< 1 ms' : '-');

    hud.innerHTML = `
      <div class="topo-hud-header">
        <div class="topo-hud-title">${escapeHtml(dev.name || dev.ip || node.name)}</div>
        <span class="tag ${cat}">${cat.replace('_', ' ').toUpperCase()}</span>
      </div>
      <div class="topo-hud-row"><span class="topo-hud-k">IP Address:</span><span class="topo-hud-v">${dev.ip || '-'}</span></div>
      <div class="topo-hud-row"><span class="topo-hud-k">MAC / Vendor:</span><span class="topo-hud-v" style="font-family:var(--font-sans);font-size:0.7rem;">${escapeHtml(dev.vendor || dev.mac || '-')}</span></div>
      <div class="topo-hud-row"><span class="topo-hud-k">Latency:</span><span class="topo-hud-v" style="color:var(--accent-green);">${ping}</span></div>
      <div class="topo-hud-ports">${ports}</div>
      <button class="btn btn-sm btn-primary topo-hud-btn" id="btn-hud-inspect">Configure & Inspect</button>
    `;

    hud.querySelector('#btn-hud-inspect')?.addEventListener('click', () => {
      hud.style.display = 'none';
      currentHoveredNodeId = null;
      openInspector(dev);
    });
  }

  const container = document.getElementById('canvas-container');
  if (container && event) {
    const rect = container.getBoundingClientRect();
    const hudW = hud.offsetWidth || 240;
    const hudH = hud.offsetHeight || 190;
    const cursorX = event.clientX - rect.left;
    const cursorY = event.clientY - rect.top;

    let x = cursorX + 24;
    let y = cursorY + 16;

    if (x + hudW > rect.width - 10) {
      x = cursorX - hudW - 24;
    }
    if (y + hudH > rect.height - 10) {
      y = cursorY - hudH - 16;
    }

    x = Math.max(10, Math.min(rect.width - hudW - 10, x));
    y = Math.max(10, Math.min(rect.height - hudH - 10, y));

    // Guarantee mouse pointer is never inside HUD boundaries to prevent flicker loops
    if (cursorX >= x - 4 && cursorX <= x + hudW + 4 && cursorY >= y - 4 && cursorY <= y + hudH + 4) {
      if (cursorY - hudH - 24 >= 10) {
        y = cursorY - hudH - 24;
      } else {
        y = cursorY + 28;
      }
    }

    hud.style.left = `${Math.round(x)}px`;
    hud.style.top = `${Math.round(y)}px`;
    hud.style.display = 'block';
  }
}

function scheduleHideNodeHud() {
  hudTimeout = setTimeout(() => {
    const hud = document.getElementById('topo-hud');
    if (hud) hud.style.display = 'none';
    currentHoveredNodeId = null;
  }, 250);
}

function renderTopology(topo) {
  const svg = document.getElementById('topo-svg');
  if (!svg) return;

  if (renderTopology._raf) {
    cancelAnimationFrame(renderTopology._raf);
  }

  renderTopology._raf = requestAnimationFrame(() => {
    renderTopology._raf = null;
    renderTopologyNow(topo, svg);
  });
}

function renderTopologyNow(topo, svg) {
  svg.innerHTML = '';

  const width = svg.clientWidth || 960;
  const height = svg.clientHeight || 600;

  // Technical Cyber Grid Definitions
  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
  defs.innerHTML = `
    <pattern id="cyber-grid" width="36" height="36" patternUnits="userSpaceOnUse">
      <circle cx="18" cy="18" r="1" fill="rgba(125, 207, 255, 0.12)" />
      <path d="M 36 0 L 0 0 0 36" fill="none" stroke="rgba(255, 255, 255, 0.025)" stroke-width="0.5"/>
    </pattern>
  `;
  svg.appendChild(defs);

  const mainG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  mainG.setAttribute('id', 'topo-main-group');
  svg.appendChild(mainG);

  // Background Grid spanning wide for panning
  const gridRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  gridRect.setAttribute('x', '-2500');
  gridRect.setAttribute('y', '-2500');
  gridRect.setAttribute('width', '7000');
  gridRect.setAttribute('height', '7000');
  gridRect.setAttribute('fill', 'url(#cyber-grid)');
  gridRect.setAttribute('pointer-events', 'none');
  mainG.appendChild(gridRect);

  const nodes = [];
  const links = [];

  // 1. Internet / WAN
  const wanNode = {
    id: 'wan',
    name: topo.wan?.isp || 'Aussie Broadband',
    sub: `${topo.wan?.ip || '117.20.69.236'} (AU)`,
    category: 'internet',
    x: width * 0.09,
    y: height * 0.50,
    r: 32,
    data: { name: 'Internet / Upstream ISP', ...topo.wan, category: 'internet' }
  };
  nodes.push(wanNode);

  // 2. NBN Modem / NTD
  const modemNode = {
    id: 'modem',
    name: 'NBN NTD (Modem)',
    sub: 'Optical Terminal',
    category: 'modem',
    x: width * 0.23,
    y: height * 0.50,
    r: 28,
    data: { ...topo.modem, category: 'modem' }
  };
  nodes.push(modemNode);
  links.push({ source: wanNode, target: modemNode, wired: true, medium: '1000/50 NBN' });

  // 3. Router (TP-Link Archer BE550 v2)
  const routerNode = {
    id: 'router',
    name: topo.router?.name || 'Archer BE550 v2',
    sub: `${topo.host?.gateway || '192.168.0.1'} (Wi-Fi 7)`,
    category: 'router',
    x: width * 0.40,
    y: height * 0.50,
    r: 36,
    data: {
      ...topo.router,
      ip: topo.host?.gateway || '192.168.0.1',
      category: 'router',
      open_ports: [80, 443, 53]
    }
  };
  nodes.push(routerNode);
  links.push({ source: modemNode, target: routerNode, wired: true, medium: '2.5G SFP+ WAN' });

  // 4. Extender (Netgear EX6250v2)
  const extDevice = topo.devices?.find(d => d.category === 'extender');
  let extenderNode = null;
  if (extDevice) {
    extenderNode = {
      id: 'extender',
      name: extDevice.name || 'Netgear EX6250v2',
      sub: `${extDevice.ip} (Mesh)`,
      category: 'extender',
      x: width * 0.57,
      y: height * 0.22,
      r: 28,
      data: extDevice
    };
    nodes.push(extenderNode);
    links.push({ source: routerNode, target: extenderNode, wired: false, medium: '5 GHz Mesh' });
  }

  // 5. Host Node (Workstation)
  const hostDev = topo.devices?.find(d => d.is_local_host) || topo.host;
  let hostNode = null;
  if (hostDev) {
    hostNode = {
      id: 'host',
      name: hostDev.name || 'Omarchy Workstation',
      sub: `${hostDev.ip || '192.168.0.5'} (Local)`,
      category: 'host',
      x: width * 0.58,
      y: height * 0.74,
      r: 28,
      data: { ...hostDev, is_local_host: true, category: 'host' }
    };
    nodes.push(hostNode);
    links.push({ source: routerNode, target: hostNode, wired: false, medium: 'Wi-Fi 7 (6 GHz)' });
  }

  // 6. Remaining Client devices partitioned into clean lanes
  const otherDevices = topo.devices?.filter(d => !d.is_gateway && d.category !== 'extender' && !d.is_local_host) || [];
  
  // Separate into Media/TVs vs Surveillance/Other
  const lane1Devices = otherDevices.filter(d => d.category === 'camera' || d.category === 'nvr');
  const lane2Devices = otherDevices.filter(d => d.category !== 'camera' && d.category !== 'nvr');

  // Place Lane 1 (Cameras/NVR at x: width * 0.78)
  lane1Devices.forEach((dev, idx) => {
    const total = Math.max(lane1Devices.length, 1);
    const clientY = (height * 0.16) + (idx / Math.max(total - 1, 1)) * (height * 0.68);
    const stableId = `cam-${dev.ip || dev.mac || idx}`;
    const cNode = {
      id: stableId,
      name: dev.name || `Cam ${dev.ip}`,
      sub: `${dev.ip}`,
      category: dev.category || 'camera',
      x: width * 0.77,
      y: total === 1 ? height * 0.40 : clientY,
      r: 24,
      data: dev
    };
    nodes.push(cNode);
    links.push({ source: routerNode, target: cNode, wired: false, medium: 'IoT VLAN (2.4 GHz)' });
  });

  // Place Lane 2 (Smart TVs, Media, PCs at x: width * 0.92)
  lane2Devices.forEach((dev, idx) => {
    const total = Math.max(lane2Devices.length, 1);
    const clientY = (height * 0.16) + (idx / Math.max(total - 1, 1)) * (height * 0.68);
    const stableId = `dev-${dev.ip || dev.mac || idx}`;
    const cNode = {
      id: stableId,
      name: dev.name || `Device ${dev.ip}`,
      sub: `${dev.ip}`,
      category: dev.category || 'unknown',
      x: width * 0.92,
      y: total === 1 ? height * 0.60 : clientY,
      r: 23,
      data: dev
    };
    nodes.push(cNode);
    const targetSource = (extenderNode && idx % 2 === 1) ? extenderNode : routerNode;
    const med = dev.category === 'smart_tv' ? '5 GHz Wi-Fi' : 'LAN';
    links.push({ source: targetSource, target: cNode, wired: false, medium: med });
  });

  // Render Links
  links.forEach(l => {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const dx = l.target.x - l.source.x;
    const dy = l.target.y - l.source.y;
    const cx1 = l.source.x + dx * 0.45;
    const cy1 = l.source.y;
    const cx2 = l.source.x + dx * 0.55;
    const cy2 = l.target.y;
    const d = `M ${l.source.x} ${l.source.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${l.target.x} ${l.target.y}`;
    
    line.setAttribute('d', d);
    line.setAttribute('fill', 'none');
    line.setAttribute('class', `topo-link ${l.wired ? 'wired' : ''}`);
    mainG.appendChild(line);

    // Link Medium Badge
    if (l.medium && dx > 90) {
      const midX = (l.source.x + l.target.x) / 2;
      const midY = (l.source.y + l.target.y) / 2 - 8;
      
      const badgeG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      badgeG.setAttribute('transform', `translate(${midX}, ${midY})`);
      
      const bText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      bText.setAttribute('class', 'link-badge-text');
      bText.textContent = l.medium;
      
      const textLen = l.medium.length * 5.2 + 10;
      const bRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      bRect.setAttribute('x', -textLen / 2);
      bRect.setAttribute('y', -7);
      bRect.setAttribute('width', textLen);
      bRect.setAttribute('height', 14);
      bRect.setAttribute('class', 'link-badge-rect');

      badgeG.appendChild(bRect);
      badgeG.appendChild(bText);
      mainG.appendChild(badgeG);
    }
  });

  // Render SVG Nodes
  nodes.forEach(n => {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    const isHighlighted = state.highlightedIps.includes(n.data?.ip);
    g.setAttribute('class', `topo-node ${isHighlighted ? 'highlighted' : ''}`);
    g.setAttribute('transform', `translate(${n.x}, ${n.y})`);

    // Invisible hit area for ultra-smooth hover target stability
    const hitArea = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    hitArea.setAttribute('r', n.r + 8);
    hitArea.setAttribute('class', 'node-hit-area');
    hitArea.setAttribute('fill', 'transparent');
    hitArea.setAttribute('stroke', 'none');
    g.appendChild(hitArea);

    // Outer glowing halo
    const glow = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    glow.setAttribute('r', n.r + 6);
    glow.setAttribute('fill', 'none');
    glow.setAttribute('class', 'node-halo');
    let glowColor = 'rgba(125, 207, 255, 0.18)';
    if (n.category === 'host') glowColor = 'rgba(158, 206, 106, 0.25)';
    if (n.category === 'camera') glowColor = 'rgba(245, 158, 11, 0.25)';
    if (n.category === 'nvr') glowColor = 'rgba(236, 72, 153, 0.25)';
    if (isHighlighted) glowColor = 'rgba(247, 118, 142, 0.6)';
    glow.setAttribute('stroke', glowColor);
    glow.setAttribute('stroke-width', isHighlighted ? '3' : '2');
    g.appendChild(glow);

    // Node Circle Background
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('r', n.r);
    circle.setAttribute('class', 'node-bg');
    if (n.category === 'router') circle.setAttribute('stroke', '#7dcfff');
    else if (n.category === 'host') circle.setAttribute('stroke', '#9ece6a');
    else if (n.category === 'camera') circle.setAttribute('stroke', '#f59e0b');
    else if (n.category === 'nvr') circle.setAttribute('stroke', '#ec4899');
    else if (n.category === 'smart_tv') circle.setAttribute('stroke', '#e0af68');
    else if (n.category === 'extender') circle.setAttribute('stroke', '#7aa2f7');
    else if (n.category === 'internet') circle.setAttribute('stroke', '#bb9af7');
    g.appendChild(circle);

    // Inner subtle ring
    const innerCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    innerCircle.setAttribute('r', n.r * 0.72);
    innerCircle.setAttribute('class', 'node-inner-circle');
    g.appendChild(innerCircle);

    // Node Vector Icon
    const iconG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    iconG.innerHTML = getNodeIconSvg(n.category, n.r);
    g.appendChild(iconG);

    // Live Ping Status Dot
    const statusDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    statusDot.setAttribute('cx', n.r * 0.7);
    statusDot.setAttribute('cy', -n.r * 0.7);
    statusDot.setAttribute('r', '4');
    statusDot.setAttribute('class', 'node-status-dot');
    let dotColor = '#10b981';
    if (n.data?.latency > 35) dotColor = '#e0af68';
    if (n.data?.latency > 80) dotColor = '#f43f5e';
    statusDot.setAttribute('fill', dotColor);
    g.appendChild(statusDot);

    // Title label below node
    const titleText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    titleText.setAttribute('y', n.r + 14);
    titleText.setAttribute('class', 'node-text-title');
    titleText.textContent = truncate(n.name, 16);
    g.appendChild(titleText);

    // Sub label
    const subText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    subText.setAttribute('y', n.r + 26);
    subText.setAttribute('class', 'node-text-sub');
    subText.textContent = n.sub;
    g.appendChild(subText);

    // Hover HUD Interactions
    g.addEventListener('mouseenter', (e) => {
      showNodeHud(n, e);
    });
    g.addEventListener('mouseleave', scheduleHideNodeHud);

    // Click Selection
    g.addEventListener('click', () => {
      document.querySelectorAll('.topo-node').forEach(nodeEl => nodeEl.classList.remove('selected'));
      g.classList.add('selected');
      const hud = document.getElementById('topo-hud');
      if (hud) hud.style.display = 'none';
      currentHoveredNodeId = null;
      openInspector(n.data);
    });

    mainG.appendChild(g);
  });

  applyTopologyTransform();
}

function truncate(str, len) {
  if (!str) return '';
  return str.length > len ? str.substring(0, len - 2) + '..' : str;
}

// -------------------------------------------------------------
// 2. NETWORK SUGGESTIONS VIEW
// -------------------------------------------------------------
function initSuggestionsFilter() {
  document.querySelectorAll('[data-sug-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-sug-filter]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.suggestionFilter = btn.getAttribute('data-sug-filter');
      if (state.topology) {
        renderSuggestions(state.topology.suggestions || []);
      }
    });
  });
}

function renderSuggestions(suggestions) {
  const container = document.getElementById('suggestions-container');
  if (!container) return;
  container.innerHTML = '';

  // Update counters
  const criticalCount = suggestions.filter(s => s.priority === 'critical').length;
  const recommendedCount = suggestions.filter(s => s.priority === 'recommended').length;
  const optCount = suggestions.filter(s => s.priority === 'optimization').length;

  document.getElementById('badge-count-critical').textContent = `${criticalCount} Critical Actions`;
  document.getElementById('badge-count-recommended').textContent = `${recommendedCount} Recommended`;
  document.getElementById('badge-count-opt').textContent = `${optCount} Optimizations`;

  // Filter
  const filtered = suggestions.filter(s => {
    if (state.suggestionFilter === 'all') return true;
    return s.priority === state.suggestionFilter;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="solution-placeholder full-width">
        <div class="placeholder-icon">✓</div>
        <h4>No suggestions in this category</h4>
        <p>All network settings in this scope meet optimal recommended configurations.</p>
      </div>
    `;
    return;
  }

  filtered.forEach(s => {
    const card = document.createElement('div');
    card.className = `suggestion-card priority-${s.priority}`;

    const stepsHtml = (s.steps || []).map(st => `<li>${st}</li>`).join('');

    card.innerHTML = `
      <div class="sug-top-bar">
        <div class="sug-badge-group">
          <span class="sug-pill ${s.priority}">${s.badge || s.priority.toUpperCase()}</span>
          <span class="sug-cat-label">${s.category}</span>
        </div>
        <button class="btn btn-sm btn-primary btn-ask-ai" data-goal="${escapeHtml(s.action_goal || s.title)}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
          Ask Agent to Solve
        </button>
      </div>

      <div class="sug-main-row">
        <div class="sug-main-text">
          <h3 class="sug-title">${s.title}</h3>
          <p class="sug-desc">${s.description}</p>
        </div>
        <button class="btn btn-sm btn-secondary sug-expand" aria-expanded="false">
          Details
        </button>
      </div>

      <div class="sug-details" hidden>
        <div class="sug-diff-box">
          <div class="diff-col current">
            <span class="diff-label">Current State</span>
            <span class="diff-val">${s.current_state}</span>
          </div>
          <div class="diff-arrow">➔</div>
          <div class="diff-col recommended">
            <span class="diff-label">Recommended State</span>
            <span class="diff-val">${s.recommended_state}</span>
          </div>
        </div>

        <div class="sug-path-box">
          <span class="path-label">Archer BE550 Menu Path:</span>
          <span class="path-val code">${s.be550_path}</span>
        </div>

        <div class="sug-steps">
          <div class="sug-steps-title">Recommended Implementation Steps:</div>
          <ol class="sug-steps-list">${stepsHtml}</ol>
        </div>
      </div>
    `;

    const expandBtn = card.querySelector('.sug-expand');
    const details = card.querySelector('.sug-details');
    if (expandBtn && details) {
      expandBtn.addEventListener('click', () => {
        const isHidden = details.hasAttribute('hidden');
        if (isHidden) {
          details.removeAttribute('hidden');
          expandBtn.textContent = 'Hide';
          expandBtn.setAttribute('aria-expanded', 'true');
        } else {
          details.setAttribute('hidden', '');
          expandBtn.textContent = 'Details';
          expandBtn.setAttribute('aria-expanded', 'false');
        }
      });
    }

    card.querySelector('.btn-ask-ai').addEventListener('click', () => {
      const goal = s.action_goal || s.title;
      const solverTab = document.querySelector('.nav-tab[data-tab="solver"]');
      if (solverTab) solverTab.click();
      const input = document.getElementById('goal-input');
      if (input) input.value = goal;
      runAgentWorkflow(goal);
    });

    container.appendChild(card);
  });
}

// -------------------------------------------------------------
// 3. AGENT STUDIO & MULTI-AGENT ORCHESTRATOR
// -------------------------------------------------------------
function initAgentStudio() {
  document.querySelectorAll('.preset-card').forEach(btn => {
    btn.addEventListener('click', () => {
      const goal = btn.getAttribute('data-goal');
      const agent = btn.getAttribute('data-agent') || 'orchestrator';
      const input = document.getElementById('goal-input');
      input.value = goal;
      const sel = document.getElementById('agent-persona-select');
      if (sel) sel.value = agent;
      runAgentWorkflow(goal, agent);
    });
  });

  document.getElementById('btn-submit-goal').addEventListener('click', () => {
    const input = document.getElementById('goal-input');
    const goal = input.value.trim();
    const agent = document.getElementById('agent-persona-select').value;
    if (goal) runAgentWorkflow(goal, agent);
  });

  document.getElementById('goal-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const goal = e.target.value.trim();
      const agent = document.getElementById('agent-persona-select').value;
      if (goal) runAgentWorkflow(goal, agent);
    }
  });
}

async function runAgentWorkflow(goal, requestedAgent = null) {
  const container = document.getElementById('solution-container');
  const chatThread = document.getElementById('agent-chat-thread');
  const agentId = requestedAgent || document.getElementById('agent-persona-select').value;
  
  if (!state.agentChatSessionId) {
    state.agentChatSessionId = `sess_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
  }

  // Render user question bubble in multi-turn thread
  if (chatThread) {
    chatThread.style.display = 'flex';
    const userMsg = document.createElement('div');
    userMsg.className = 'chat-message chat-user';
    userMsg.innerHTML = `
      <div class="chat-bubble">
        <div class="chat-text">${escapeHtml(goal)}</div>
      </div>
      <div class="chat-avatar">👤</div>
    `;
    chatThread.appendChild(userMsg);
    chatThread.scrollTop = chatThread.scrollHeight;
  }

  const activeEngine = state.config.ai_provider === 'gemini' && state.config.gemini_has_key
    ? `Google Gemini (${state.config.gemini_model || 'gemini-2.0-flash'})`
    : (state.config.ai_provider === 'mistral' && state.config.mistral_has_key
      ? `Mistral AI (${state.config.mistral_model})`
      : (state.config.ai_provider === 'openrouter' && state.config.openrouter_has_key
        ? `OpenRouter (${state.config.openrouter_model})`
        : 'Local Multi-Agent Engine'));
  
  container.innerHTML = `
    <div class="solution-placeholder">
      <div class="placeholder-icon rotating">⚙️</div>
      <h4>Agent Orchestrator Initializing Workflow...</h4>
      <p>Executing live diagnostic tools (<code>tool_ping</code>, <code>tool_portscan</code>, <code>tool_read_docs</code>) using <strong>${activeEngine}</strong>...</p>
      <div class="agent-thinking-bar">
        <span class="thinking-dot"></span>
        <span class="thinking-text">Dispatching specialized agents and synthesizing network solution...</span>
      </div>
    </div>
  `;

  try {
    const res = await fetch('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.agentChatSessionId,
        message: goal,
        agent: agentId
      })
    });
    const solution = await res.json();
    
    // Render agent answer bubble in chat thread
    if (chatThread) {
      const agentMsg = document.createElement('div');
      agentMsg.className = 'chat-message chat-agent';
      const lead = solution.lead_agent || { name: 'NetMap Agent Orchestrator', icon: '🧠', role: 'Network Dispatcher' };
      agentMsg.innerHTML = `
        <div class="chat-avatar">${lead.icon || '🧠'}</div>
        <div class="chat-bubble">
          <div class="chat-author">${lead.name} <span class="chat-role">• ${solution.ai_engine || 'NetMap AI'}</span></div>
          <div class="chat-text">${formatMarkdown(solution.summary || 'Solution generated below.')}</div>
        </div>
      `;
      chatThread.appendChild(agentMsg);
      chatThread.scrollTop = chatThread.scrollHeight;
    }

    renderSolution(solution);
  } catch (err) {
    container.innerHTML = `
      <div class="alert-box warning">
        <div class="alert-title">Agent Workflow Error</div>
        <div>Failed to contact agent orchestrator: ${err.message}</div>
      </div>
    `;
    showToast(`Agent error: ${err.message}`, "error");
  }
}

function renderSolution(sol) {
  const container = document.getElementById('solution-container');
  container.innerHTML = '';

  // Track highlighted IPs
  state.highlightedIps = sol.highlight_nodes || [];

  const leadAgent = sol.lead_agent || { name: 'NetMap Agent Orchestrator', icon: '🧠', role: 'Network Dispatcher' };

  // 0. EXACT WIRING/PORT MAPPING ANSWER CARD (shown first when available)
  const exact = sol.exact_mapping;
  if (exact && exact.source && exact.target) {
    const mappingCard = document.createElement('div');
    mappingCard.className = 'exact-mapping-card';
    mappingCard.innerHTML = `
      <div class="exact-mapping-header">
        <div class="exact-mapping-title">
          <span class="exact-mapping-icon">🔌</span>
          <span>Exact Port-to-Port Mapping</span>
        </div>
        <span class="exact-mapping-badge confidence-${exact.confidence || 'medium'}">
          ${(exact.confidence || 'medium').toUpperCase()} CONFIDENCE
        </span>
      </div>
      <div class="exact-mapping-body">
        <div class="exact-mapping-endpoint">
          <div class="exact-mapping-device">${escapeHtml(exact.source.device || 'Router')}</div>
          <div class="exact-mapping-ip">${escapeHtml(exact.source.ip || '')}</div>
          <div class="exact-mapping-port">${escapeHtml(exact.source.port || 'LAN1')}</div>
          <div class="exact-mapping-label">${escapeHtml(exact.source.label || 'LAN 1')}</div>
        </div>
        <div class="exact-mapping-center">
          <div class="exact-mapping-cable">${escapeHtml(exact.cable || 'Cat 6')}</div>
          <div class="exact-mapping-speed">${escapeHtml(exact.speed || '')}</div>
          <div class="exact-mapping-arrow">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"></line>
              <polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </div>
        </div>
        <div class="exact-mapping-endpoint">
          <div class="exact-mapping-device">${escapeHtml(exact.target.device || 'Device')}</div>
          <div class="exact-mapping-ip">${escapeHtml(exact.target.ip || '')}</div>
          <div class="exact-mapping-port">${escapeHtml(exact.target.port || 'LAN1')}</div>
          <div class="exact-mapping-label">${escapeHtml(exact.target.label || 'LAN 1')}</div>
        </div>
      </div>
      ${exact.reasoning ? `<div class="exact-mapping-reasoning">${escapeHtml(exact.reasoning)}</div>` : ''}
      <button class="btn btn-sm btn-secondary exact-mapping-topo" onclick="switchToTopologyAndHighlight()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
        Show on Topology Map
      </button>
    `;
    container.appendChild(mappingCard);
  }

  // 1. LEAD AGENT & HEADER CARD
  const header = document.createElement('div');
  header.className = 'solution-header-card';
  header.innerHTML = `
    <div style="flex:1;">
      <div class="agent-lead-row">
        <span class="agent-lead-avatar">${leadAgent.icon || '🧠'}</span>
        <div>
          <div class="agent-lead-name">${leadAgent.name}</div>
          <div class="agent-lead-role">${leadAgent.role} • ${sol.ai_engine || 'NetMap AI'}</div>
        </div>
      </div>
      <h3 class="sol-title" style="margin-top:10px;">${sol.goal}</h3>
      <div class="sol-summary">${formatMarkdown(sol.summary || '')}</div>
    </div>
    ${sol.highlight_nodes && sol.highlight_nodes.length > 0 ? `
      <button class="btn btn-sm btn-primary" onclick="switchToTopologyAndHighlight()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
        Highlight Nodes on Map
      </button>
    ` : ''}
  `;
  container.appendChild(header);

  // 2. LIVE AGENT EXECUTION TRACE & TOOL INVOCATIONS
  if (sol.agent_trace && sol.agent_trace.length > 0) {
    const traceCard = document.createElement('div');
    traceCard.className = 'agent-trace-card';
    
    let traceStepsHtml = '';
    sol.agent_trace.forEach(t => {
      traceStepsHtml += `
        <div class="trace-step-item">
          <div class="trace-step-icon">${t.icon || '⚙️'}</div>
          <div class="trace-step-body">
            <div class="trace-step-header">
              <span class="trace-agent-label">${t.agent}</span>
              <span class="trace-tool-pill">Tool: ${t.tool}</span>
            </div>
            <div class="trace-thought">${formatMarkdown(t.thought || '')}</div>
            <div class="trace-result code">${escapeHtml(t.result || '')}</div>
          </div>
        </div>
      `;
    });

    traceCard.innerHTML = `
      <details class="trace-accordion">
        <summary class="trace-summary-header">
          <span>🔍 Agent Execution Trace & Tool Invocations (${sol.agent_trace.length} Steps)</span>
          <span class="trace-collapse-hint">Click to toggle</span>
        </summary>
        <div class="trace-steps-container">
          ${traceStepsHtml}
        </div>
      </details>
    `;
    container.appendChild(traceCard);
  }

  // 3. INTERACTIVE ACTIONABLE BUTTONS
  if (sol.action_items && sol.action_items.length > 0) {
    const actionsCard = document.createElement('div');
    actionsCard.className = 'action-buttons-card';
    
    let btnsHtml = '';
    sol.action_items.forEach((act, idx) => {
      btnsHtml += `
        <button class="btn-action-exec" data-act-idx="${idx}">
          <span class="btn-act-icon">${act.icon || '⚡'}</span>
          <span class="btn-act-label">${act.label}</span>
        </button>
      `;
    });

    actionsCard.innerHTML = `
      <div class="action-card-header">
        <span class="action-card-title">⚡ Interactive Diagnostic & Configuration Actions</span>
        <span class="action-card-sub">Click any action to execute immediately via NetMap tools</span>
      </div>
      <div class="action-buttons-grid">
        ${btnsHtml}
      </div>
      <div id="action-result-box" class="action-result-box" style="display:none;"></div>
    `;

    // Attach click listeners to action buttons
    actionsCard.querySelectorAll('.btn-action-exec').forEach(btn => {
      btn.addEventListener('click', async () => {
        const idx = parseInt(btn.getAttribute('data-act-idx'));
        const act = sol.action_items[idx];
        await executeAgentAction(act);
      });
    });

    container.appendChild(actionsCard);
  }

  // 4. MERMAID ARCHITECTURAL DIAGRAM
  if (sol.mermaid && typeof sol.mermaid === 'string' && sol.mermaid.trim().length > 0) {
    const mCard = document.createElement('div');
    mCard.className = 'mermaid-visual-card';
    mCard.innerHTML = `
      <div class="visual-flow-header">
        <span class="visual-flow-title">📊 Architectural Network Diagram (Mermaid)</span>
      </div>
      <div class="mermaid-container">
        <pre class="mermaid">${sol.mermaid}</pre>
      </div>
    `;
    container.appendChild(mCard);
    if (window.mermaid) {
      setTimeout(() => {
        try {
          mermaid.run();
        } catch (e) {
          console.warn("Mermaid error:", e);
        }
      }, 50);
    }
  }

  // 5. NATIVE VISUAL FLOWCHART CARD (NODES & LINKS)
  if (sol.visual_diagram && sol.visual_diagram.nodes && sol.visual_diagram.nodes.length > 0) {
    const vCard = document.createElement('div');
    vCard.className = 'visual-flow-card';
    
    let nodesHtml = '';
    const vNodes = sol.visual_diagram.nodes;
    const vLinks = sol.visual_diagram.links || [];

    vNodes.forEach((node, i) => {
      const stepNum = String(i + 1).padStart(2, '0');
      nodesHtml += `
        <div class="flow-step-node" style="border-color:${node.color || 'var(--border-hover)'}">
          <span class="flow-step-num">${stepNum}</span>
          <div class="flow-node-icon">${node.icon || '📦'}</div>
          <div class="flow-node-label">${escapeHtml(node.label)}</div>
          <div class="flow-node-sub">${escapeHtml(node.sub || '')}</div>
        </div>
      `;

      if (i < vNodes.length - 1) {
        const link = vLinks[i] || { label: 'Data Flow' };
        nodesHtml += `
          <div class="flow-arrow-col">
            <span class="flow-arrow-label">${escapeHtml(link.label || 'Direct Link')}</span>
            <span class="flow-arrow-line">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </span>
          </div>
        `;
      }
    });

    vCard.innerHTML = `
      <div class="visual-flow-header">
        <span class="visual-flow-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;color:var(--accent-cyan);"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
          Interactive Visual Flow: ${escapeHtml(sol.visual_diagram.title || 'Architecture & Protocol Pipeline')}
        </span>
      </div>
      <div class="flow-container">
        ${nodesHtml}
      </div>
    `;
    container.appendChild(vCard);
  }

  // 6. ROUTER CONFIG PREVIEW CARD
  if (sol.router_config_card && sol.router_config_card.fields) {
    const rc = document.createElement('div');
    rc.className = 'router-config-preview';
    let fieldsHtml = '';
    sol.router_config_card.fields.forEach(f => {
      fieldsHtml += `
        <div class="config-field-box">
          <div class="config-field-label">${f.label}</div>
          <div class="config-field-value">${f.value}</div>
        </div>
      `;
    });

    rc.innerHTML = `
      <div class="router-config-title">
        <span>⚙️ Archer BE550 Required Settings</span>
        <span style="font-size:0.7rem;color:var(--text-dim);">Path: ${sol.router_config_card.page || 'Virtual Servers'}</span>
      </div>
      <div class="router-config-grid">
        ${fieldsHtml}
      </div>
    `;
    container.appendChild(rc);
  }

  // 7. WARNINGS & ALERTS
  if (sol.warnings && sol.warnings.length > 0) {
    sol.warnings.forEach(w => {
      const alert = document.createElement('div');
      alert.className = `alert-box ${w.type || 'caution'}`;
      alert.innerHTML = `
        <div class="alert-title">${formatMarkdown(w.title || '')}</div>
        <div>${formatMarkdown(w.text || '')}</div>
      `;
      container.appendChild(alert);
    });
  }

  // 8. NUMBERED STEP-BY-STEP TEXT INSTRUCTIONS
  if (sol.steps && sol.steps.length > 0) {
    sol.steps.forEach(s => {
      const step = document.createElement('div');
      step.className = 'step-card';
      
      let cmdHtml = '';
      if (s.command) {
        cmdHtml = `
          <div class="code-block">
            <code>${escapeHtml(s.command)}</code>
            <button class="btn-copy" onclick="copyText('${escapeHtml(s.command)}')">Copy</button>
          </div>
        `;
      }

      step.innerHTML = `
        <div class="step-num">${s.step}</div>
        <div class="step-content">
          <div class="step-heading">${formatMarkdown(s.title || '')}</div>
          <div class="step-details">${formatMarkdown(s.details || '')}</div>
          ${cmdHtml}
        </div>
      `;
      container.appendChild(step);
    });
  }

  // 9. BEST PRACTICES
  if (sol.best_practices && sol.best_practices.length > 0) {
    const tips = document.createElement('div');
    tips.className = 'tips-card';
    tips.innerHTML = `
      <h5>💡 Best Practices for Your Archer BE550 & AussieBB Network</h5>
      <ul>
        ${sol.best_practices.map(bp => `<li>${formatMarkdown(bp)}</li>`).join('')}
      </ul>
    `;
    container.appendChild(tips);
  }

  // 10. QUICK CONVERSATIONAL FOLLOW-UP CHIPS
  if (sol.quick_followups && sol.quick_followups.length > 0) {
    const qfCard = document.createElement('div');
    qfCard.className = 'quick-followups-card';
    qfCard.innerHTML = `
      <div class="quick-followups-header">
        <span class="quick-followups-icon">💬</span>
        <span class="quick-followups-title">Suggested Follow-Up Inquiries</span>
        <span class="quick-followups-sub">Click any question to ask the agent:</span>
      </div>
      <div class="quick-followups-chips">
        ${sol.quick_followups.map(q => `<button class="chip-followup" data-query="${escapeHtml(q)}">${escapeHtml(q)}</button>`).join('')}
      </div>
    `;
    qfCard.querySelectorAll('.chip-followup').forEach(chip => {
      chip.addEventListener('click', () => {
        const query = chip.getAttribute('data-query');
        const input = document.getElementById('goal-input');
        if (input) input.value = query;
        runAgentWorkflow(query);
      });
    });
    container.appendChild(qfCard);
  }
}

async function executeAgentAction(act) {
  const resultBox = document.getElementById('action-result-box');
  if (resultBox) {
    resultBox.style.display = 'block';
    resultBox.innerHTML = `Running action: <strong>${escapeHtml(act.label)}</strong>...`;
  }
  showToast(`Running action: ${act.label}`, "info");

  try {
    const res = await fetch('/api/agent/execute-action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: act.type,
        params: act.params
      })
    });
    const data = await res.json();
    
    if (resultBox) {
      if (act.type === 'tool_ping') {
        const ping = data.result;
        resultBox.innerHTML = `
          <div class="action-res-header">✓ Latency Test Result: ${escapeHtml(act.params.host || '')}</div>
          <div class="action-res-body">Reachable: <strong>${ping.reachable}</strong> | Avg: <strong>${ping.avg || '-'} ms</strong> (Min: ${ping.min || '-'} ms, Max: ${ping.max || '-'} ms, Jitter: ±${ping.mdev || '-'} ms)</div>
        `;
      } else if (act.type === 'tool_portscan') {
        const ps = data.result;
        resultBox.innerHTML = `
          <div class="action-res-header">✓ Port Scan Result: ${escapeHtml(act.params.ip || '')}</div>
          <div class="action-res-body">Open Ports Found: <strong>${ps.open_ports?.join(', ') || 'None'}</strong> (Tested: ${ps.scanned?.join(', ')})</div>
        `;
      } else if (act.type === 'tool_read_docs') {
        const doc = data.result;
        resultBox.innerHTML = `
          <div class="action-res-header">✓ Knowledge Base Loaded: ${escapeHtml(doc.title || '')}</div>
          <div class="action-res-body">File: <code>${escapeHtml(doc.filename || '')}</code>. <button class="btn btn-sm btn-secondary" onclick="openDocById('${(doc.filename || '').replace('.md', '')}')">View Full Document</button></div>
        `;
      } else if (act.type === 'tool_wifi_spectrum') {
        const spec = data.result;
        const aps = spec.networks || [];
        const topAps = aps.slice(0, 5).map(ap => `
          <div style="font-size:0.75rem;padding:3px 0;display:flex;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,0.04);">
            <span><strong>${escapeHtml(ap.ssid || '<Hidden>')}</strong> (Ch ${ap.channel || '-'}, ${ap.freq_mhz || '-'} MHz)</span>
            <span style="color:${ap.signal_dbm > -65 ? 'var(--accent-green)' : (ap.signal_dbm > -75 ? 'var(--accent-yellow)' : 'var(--accent-red)')};">${ap.signal_dbm || '-'} dBm (${ap.quality || '-'}%)</span>
          </div>
        `).join('');

        resultBox.innerHTML = `
          <div class="action-res-header">✓ Wi-Fi Spectrum Survey Complete (${spec.total_networks || aps.length} Access Points Detected)</div>
          <div class="action-res-body" style="margin-bottom:8px;">
            Recommended 2.4 GHz Channel: <strong>Channel ${spec.recommended_2ghz_channel || '1'}</strong> (Interference Score: ${spec.interference_2ghz?.[spec.recommended_2ghz_channel] || 'Low'})<br/>
            Recommended 5 GHz Channel: <strong>Channel ${spec.recommended_5ghz_channel || '36'}</strong> (Clean UNII-1/3)
          </div>
          ${topAps ? `<div style="margin-top:6px;"><div style="font-weight:700;font-size:0.75rem;color:var(--text-dim);margin-bottom:4px;">Strongest Nearby Access Points:</div>${topAps}</div>` : ''}
        `;
      } else if (act.type === 'tool_bufferbloat') {
        const bb = data.result;
        const gradeColor = bb.grade === 'A+' || bb.grade === 'A' ? 'var(--accent-green)' : (bb.grade === 'B' ? 'var(--accent-cyan)' : (bb.grade === 'C' ? 'var(--accent-yellow)' : 'var(--accent-red)'));
        resultBox.innerHTML = `
          <div class="action-res-header">✓ Bufferbloat Benchmark Complete: <span style="color:${gradeColor};font-size:1.1em;font-weight:800;">Grade ${bb.grade || 'A'}</span></div>
          <div class="action-res-body">
            Target: <strong>${bb.target_ip || '1.1.1.1'}</strong> | Unloaded: <strong>${bb.unloaded_latency_ms?.toFixed(1) || '-'} ms</strong> | Loaded: <strong>${bb.loaded_latency_ms?.toFixed(1) || '-'} ms</strong> | Bloat Delta: <strong style="color:${gradeColor}">+${bb.bufferbloat_delta_ms?.toFixed(1) || '0'} ms</strong> | Loss: <strong>${bb.packet_loss_pct || 0}%</strong><br/>
            <span style="font-size:0.76rem;color:var(--text-muted);margin-top:4px;display:inline-block;">Verdict: ${escapeHtml(bb.recommendation || 'Network buffer latency is optimal.')}</span>
          </div>
        `;
      } else if (act.type === 'tool_wake_on_lan') {
        const wol = data.result;
        resultBox.innerHTML = `
          <div class="action-res-header">✓ Wake-on-LAN Magic Packet Dispatched</div>
          <div class="action-res-body">${escapeHtml(wol.message || `Magic packet sent to ${wol.mac || 'target device'}`)} via UDP port ${wol.port || 9}.</div>
        `;
      } else if (act.type === 'tool_router_audit') {
        const audit = data.result;
        resultBox.innerHTML = `
          <div class="action-res-header">✓ Archer BE550 Gateway Audit</div>
          <div class="action-res-body">
            Status: <strong>${audit.logged_in ? 'Authenticated' : 'Offline/Unauthenticated'}</strong> | Model: <strong>${audit.model || 'Archer BE550'}</strong> | Firmware: <strong>${audit.firmware || 'Latest'}</strong><br/>
            WAN IP: <strong>${audit.wan_ip || 'DHCP'}</strong> | CGNAT Detected: <strong>${audit.is_cgnat ? 'Yes (100.64.0.0/10)' : 'No (Public IP)'}</strong>
          </div>
        `;
      } else {
        resultBox.innerHTML = `
          <div class="action-res-header">✓ Action Executed: ${escapeHtml(act.label)}</div>
          <div class="action-res-body"><pre style="font-size:0.75rem;margin:0;">${escapeHtml(JSON.stringify(data.result, null, 2))}</pre></div>
        `;
      }
    }
    showToast("Action executed successfully", "success");
  } catch (err) {
    if (resultBox) resultBox.innerHTML = `<span style="color:var(--accent-red)">Failed: ${escapeHtml(err.message)}</span>`;
    showToast(`Action failed: ${err.message}`, "error");
  }
}

window.switchToTopologyAndHighlight = function() {
  const topoTab = document.querySelector('.nav-tab[data-tab="topology"]');
  if (topoTab) topoTab.click();
  showToast("Highlighted affected nodes on topology map", "info");
};

function formatMarkdown(text) {
  if (!text) return '';

  // 1. Isolate code blocks
  const codeBlocks = [];
  let s = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
    const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    codeBlocks.push(`
      <div class="code-block">
        <pre><code>${escaped}</code></pre>
        <button class="btn-copy" onclick="copyText('${escaped.replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, '\\n')}')">Copy</button>
      </div>
    `);
    return placeholder;
  });

  // 2. Inline code `code`
  s = s.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

  // 3. Bold **text** and __text__
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>');

  // 4. Italic *text* and _text_
  s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // 5. Markdown links [text](url)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // 6. Parse lists line-by-line
  const lines = s.split('\n');
  let inUl = false;
  let inOl = false;
  const processed = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const bulletMatch = line.match(/^\s*[-*+]\s+(.*)$/);
    const numMatch = line.match(/^\s*(\d+)\.\s+(.*)$/);

    if (bulletMatch) {
      if (inOl) { processed.push('</ol>'); inOl = false; }
      if (!inUl) { processed.push('<ul class="formatted-list">'); inUl = true; }
      processed.push(`<li>${bulletMatch[1]}</li>`);
    } else if (numMatch) {
      if (inUl) { processed.push('</ul>'); inUl = false; }
      if (!inOl) { processed.push('<ol class="formatted-num-list">'); inOl = true; }
      processed.push(`<li>${numMatch[2]}</li>`);
    } else {
      if (inUl) { processed.push('</ul>'); inUl = false; }
      if (inOl) { processed.push('</ol>'); inOl = false; }
      processed.push(line);
    }
  }
  if (inUl) processed.push('</ul>');
  if (inOl) processed.push('</ol>');

  let html = processed.join('\n');

  // Convert newlines to linebreaks
  html = html.replace(/\n\n+/g, '<br/><br/>').replace(/\n/g, '<br/>');
  html = html.replace(/<br\/>\s*(<\/?(ul|ol|li|div|pre|blockquote)[^>]*>)/gi, '$1');
  html = html.replace(/(<\/?(ul|ol|li|div|pre|blockquote)[^>]*>)\s*<br\/>/gi, '$1');

  // Restore code blocks
  codeBlocks.forEach((cb, idx) => {
    html = html.replace(`__CODE_BLOCK_${idx}__`, cb);
  });

  return html;
}

function formatLinks(text) {
  return formatMarkdown(text);
}

function escapeHtml(str) {
  return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

window.copyText = function(text) {
  navigator.clipboard.writeText(text);
  showToast("Copied command to clipboard!", "success");
};

// -------------------------------------------------------------
// 4. AI DOCUMENTATION & KNOWLEDGE BASE EXPLORER
// -------------------------------------------------------------
function initDocumentation() {
  document.getElementById('btn-ask-doc-agent')?.addEventListener('click', () => {
    if (!state.activeDocId) return;
    const activeDoc = state.docs.find(d => d.id === state.activeDocId);
    const title = activeDoc ? activeDoc.title : state.activeDocId;
    const goal = `Explain the key configuration steps and best practices from the ${title} guide.`;
    
    const solverTab = document.querySelector('.nav-tab[data-tab="solver"]');
    if (solverTab) solverTab.click();
    const input = document.getElementById('goal-input');
    if (input) input.value = goal;
    runAgentWorkflow(goal);
  });
}

async function loadDocumentationIndex() {
  const sidebar = document.getElementById('docs-sidebar-list');
  if (!sidebar) return;
  sidebar.innerHTML = '<div style="padding:12px;color:var(--text-dim);font-size:0.8rem;">Loading articles...</div>';

  try {
    const res = await fetch('/api/docs');
    const data = await res.json();
    state.docs = data.articles || [];
    renderDocsSidebar(state.docs);
    
    // Load first document if none active
    if (!state.activeDocId && state.docs.length > 0) {
      loadDocArticle(state.docs[0].id);
    }
  } catch (err) {
    sidebar.innerHTML = '<div style="padding:12px;color:var(--accent-red);font-size:0.8rem;">Failed to load documentation</div>';
  }
}

function renderDocsSidebar(articles) {
  const sidebar = document.getElementById('docs-sidebar-list');
  if (!sidebar) return;
  sidebar.innerHTML = '';

  articles.forEach(a => {
    const btn = document.createElement('button');
    btn.className = `doc-nav-item ${a.id === state.activeDocId ? 'active' : ''}`;
    btn.innerHTML = `
      <div class="doc-nav-title">${a.title}</div>
      <div class="doc-nav-file">${a.filename}</div>
    `;
    btn.addEventListener('click', () => {
      loadDocArticle(a.id);
    });
    sidebar.appendChild(btn);
  });
}

async function loadDocArticle(docId) {
  state.activeDocId = docId;
  renderDocsSidebar(state.docs);

  const titleEl = document.getElementById('doc-active-title');
  const metaEl = document.getElementById('doc-active-meta');
  const contentEl = document.getElementById('doc-body-content');

  contentEl.innerHTML = '<div style="padding:20px;color:var(--text-dim);">Loading technical guide...</div>';

  try {
    const res = await fetch(`/api/docs?id=${encodeURIComponent(docId)}`);
    const data = await res.json();
    
    if (data.found) {
      titleEl.textContent = data.title;
      metaEl.textContent = `Knowledge Base File: netmap/docs/${data.filename}`;
      contentEl.innerHTML = renderMarkdown(data.content);
    } else {
      contentEl.innerHTML = `<div class="alert-box warning">Article not found: ${data.error}</div>`;
    }
  } catch (err) {
    contentEl.innerHTML = `<div class="alert-box warning">Failed to fetch guide: ${err.message}</div>`;
  }
}

window.openDocById = function(docId) {
  const docsTab = document.querySelector('.nav-tab[data-tab="docs"]');
  if (docsTab) docsTab.click();
  loadDocArticle(docId);
};

// Lightweight Client-Side Markdown Renderer
function renderMarkdown(md) {
  if (!md) return '';
  let html = md;

  // Code blocks ```lang ... ```
  html = html.replace(/```([a-z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre class="code-block-doc"><code>${escapeHtml(code.trim())}</code></pre>`;
  });

  // Inline code `...`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Headings
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^#### (.*$)/gim, '<h4>$1</h4>');

  // Bold & Italic
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Blockquotes
  html = html.replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>');

  // Unordered list items
  html = html.replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/gims, '<ul>$1</ul>');

  // Markdown links
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // Paragraphs
  html = html.split('\n\n').map(p => {
    p = p.trim();
    if (!p.startsWith('<h') && !p.startsWith('<pre') && !p.startsWith('<ul') && !p.startsWith('<blockquote') && !p.startsWith('<table')) {
      return `<p>${p}</p>`;
    }
    return p;
  }).join('\n');

  return html;
}

// -------------------------------------------------------------
// 5. DEVICE TABLE INVENTORY & FILTERING
// -------------------------------------------------------------
function initDeviceToolbar() {
  const searchInput = document.getElementById('device-search-input');
  const clearBtn = document.getElementById('btn-clear-search');
  
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      state.deviceSearch = e.target.value.toLowerCase().trim();
      if (clearBtn) clearBtn.style.display = e.target.value ? 'inline-block' : 'none';
      if (state.topology) renderDeviceTable(state.topology.devices || []);
    });
  }

  if (clearBtn && searchInput) {
    clearBtn.addEventListener('click', () => {
      searchInput.value = '';
      state.deviceSearch = '';
      clearBtn.style.display = 'none';
      if (state.topology) renderDeviceTable(state.topology.devices || []);
      searchInput.focus();
    });
  }

  document.querySelectorAll('[data-dev-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-dev-filter]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.deviceFilter = btn.getAttribute('data-dev-filter');
      if (state.topology) renderDeviceTable(state.topology.devices || []);
    });
  });
}

function renderDeviceTable(devices) {
  const tbody = document.getElementById('device-table-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  // Update counts
  const countAll = devices.length;
  const countCam = devices.filter(d => d.category === 'camera' || d.category === 'nvr').length;
  const countTv = devices.filter(d => d.category === 'smart_tv' || d.name?.includes('TV')).length;
  const countPc = devices.filter(d => d.category === 'pc' || d.category === 'host').length;
  const countNet = devices.filter(d => d.category === 'router' || d.category === 'extender').length;
  const countCustom = devices.filter(d => d.user_settings && (d.user_settings.alias || d.user_settings.role || Object.keys(d.user_settings.custom_fields || {}).length > 0)).length;

  document.getElementById('count-all').textContent = countAll;
  document.getElementById('count-cam').textContent = countCam;
  document.getElementById('count-tv').textContent = countTv;
  document.getElementById('count-pc').textContent = countPc;
  document.getElementById('count-net').textContent = countNet;
  document.getElementById('count-custom').textContent = countCustom;

  // Filter
  const filtered = devices.filter(dev => {
    if (state.deviceSearch) {
      const q = state.deviceSearch;
      const alias = dev.user_settings?.alias?.toLowerCase() || '';
      const name = dev.name?.toLowerCase() || '';
      const ip = dev.ip?.toLowerCase() || '';
      const mac = dev.mac?.toLowerCase() || '';
      const vendor = dev.vendor?.toLowerCase() || '';
      const role = dev.user_settings?.role?.toLowerCase() || '';
      const loc = dev.user_settings?.location?.toLowerCase() || '';
      const match = alias.includes(q) || name.includes(q) || ip.includes(q) || mac.includes(q) || vendor.includes(q) || role.includes(q) || loc.includes(q);
      if (!match) return false;
    }

    if (state.deviceFilter === 'all') return true;
    if (state.deviceFilter === 'camera') return dev.category === 'camera' || dev.category === 'nvr';
    if (state.deviceFilter === 'smart_tv') return dev.category === 'smart_tv' || dev.name?.includes('TV');
    if (state.deviceFilter === 'pc') return dev.category === 'pc' || dev.category === 'host';
    if (state.deviceFilter === 'router') return dev.category === 'router' || dev.category === 'extender';
    if (state.deviceFilter === 'custom') return dev.user_settings && (dev.user_settings.alias || dev.user_settings.role || Object.keys(dev.user_settings.custom_fields || {}).length > 0);

    return true;
  });

  if (filtered.length === 0) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td colspan="7" style="text-align:center;padding:36px 18px;color:var(--text-muted);">
        <div style="font-size:1.8rem;margin-bottom:8px;">🔍</div>
        <div style="font-weight:600;color:var(--text-dim);">No devices match the current filter or search query</div>
        <div style="font-size:0.75rem;margin-top:4px;">Try clearing your search or switching to "All Devices"</div>
      </td>
    `;
    tbody.appendChild(tr);
    return;
  }

  filtered.forEach(dev => {
    const tr = document.createElement('tr');
    
    const cat = dev.category || 'unknown';
    const tag = `<span class="tag ${cat}">${cat.replace('_', ' ').toUpperCase()}</span>`;
    
    const userS = dev.user_settings || {};
    const roleBadge = userS.role ? `<div class="device-role-badge">${userS.role}</div>` : '';
    const locBadge = userS.location ? `<div class="device-loc-badge">📍 ${userS.location}</div>` : '';
    const qosBadge = userS.priority && userS.priority.startsWith('High') ? '<span class="tag router" style="margin-left:4px;">QoS High</span>' : '';

    const ports = (dev.open_ports || []).map(p => {
      const isCamPort = [554, 8554, 8000, 37777, 8899, 7443].includes(p);
      return `<span class="port-tag ${isCamPort ? 'cam' : ''}">${p}</span>`;
    }).join(' ') || '<span class="text-muted" style="font-size:0.7rem;">None detected</span>';
    
    // Colored Latency Badge
    let latencyBadge = '<span class="latency-pill offline">-</span>';
    if (dev.latency) {
      const lat = dev.latency;
      if (lat < 5) {
        latencyBadge = `<span class="latency-pill excellent"><span class="pill-dot emerald" style="width:6px;height:6px;"></span>${lat.toFixed(1)} ms</span>`;
      } else if (lat < 30) {
        latencyBadge = `<span class="latency-pill good"><span class="pill-dot blue" style="width:6px;height:6px;"></span>${lat.toFixed(1)} ms</span>`;
      } else {
        latencyBadge = `<span class="latency-pill moderate"><span class="pill-dot amber" style="width:6px;height:6px;"></span>${lat.toFixed(1)} ms</span>`;
      }
    } else if (dev.is_gateway) {
      latencyBadge = `<span class="latency-pill excellent"><span class="pill-dot emerald" style="width:6px;height:6px;"></span>< 1 ms</span>`;
    }

    const canWol = Boolean(dev.mac && dev.mac.length >= 12);

    tr.innerHTML = `
      <td>
        <div class="device-cell">
          <div class="device-avatar">${ICONS[dev.category] || '⚙️'}</div>
          <div>
            <div class="device-name-text">${escapeHtml(dev.name || dev.ip)} ${qosBadge}</div>
            <div class="device-model-text">${escapeHtml(dev.original_name ? `Original: ${dev.original_name}` : (dev.model || dev.description || ''))}</div>
          </div>
        </div>
      </td>
      <td>
        ${tag}
        ${roleBadge}
      </td>
      <td class="code">${dev.ip}</td>
      <td>
        <div class="code">${dev.mac || '-'}</div>
        <div style="font-size:0.7rem;color:var(--text-muted);">${escapeHtml(dev.vendor || '')}</div>
        ${locBadge}
      </td>
      <td>
        <div style="font-size:0.75rem;margin-bottom:4px;color:var(--text-dim);">${escapeHtml(userS.network_segment || 'Main LAN')}</div>
        <div>${ports}</div>
      </td>
      <td>${latencyBadge}</td>
      <td>
        <div class="row-actions-group">
          <button class="btn-row-action btn-copy-ip" data-ip="${dev.ip}" title="Copy IP to clipboard">📋</button>
          ${canWol ? `<button class="btn-row-action btn-row-wol" data-mac="${dev.mac}" data-ip="${dev.ip}" title="Send Wake-on-LAN packet">⚡ WoL</button>` : ''}
          <button class="btn-row-action btn-row-inspect btn-inspect" data-ip="${dev.ip}">Inspect</button>
        </div>
      </td>
    `;

    tr.querySelector('.btn-inspect').addEventListener('click', () => {
      openInspector(dev);
    });

    tr.querySelector('.btn-copy-ip')?.addEventListener('click', (e) => {
      e.stopPropagation();
      navigator.clipboard.writeText(dev.ip);
      showToast(`Copied ${dev.ip} to clipboard`, "success", 2000);
    });

    tr.querySelector('.btn-row-wol')?.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        const res = await fetch('/api/devices/wol', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mac: dev.mac, ip: dev.ip })
        });
        const data = await res.json();
        showToast(data.message || `Sent WoL packet to ${dev.name || dev.ip}`, 'success');
      } catch (err) {
        showToast('Failed to send WoL packet: ' + err.message, 'error');
      }
    });

    tbody.appendChild(tr);
  });
}

// -------------------------------------------------------------
// 6. NODE INSPECTOR & PER-DEVICE CUSTOM SETTINGS EDITOR
// -------------------------------------------------------------
function initInspector() {
  const drawer = document.getElementById('inspector-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  const closeBtn = document.getElementById('btn-close-drawer');

  const closeDrawer = () => {
    drawer.classList.remove('open');
    backdrop.classList.remove('open');
  };

  closeBtn.addEventListener('click', closeDrawer);
  backdrop.addEventListener('click', closeDrawer);

  document.querySelectorAll('.drawer-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.drawer-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.drawer-pane').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.getAttribute('data-dtab');
      document.getElementById(`dpane-${target}`).classList.add('active');
    });
  });

  document.getElementById('btn-add-custom-field').addEventListener('click', () => {
    addCustomFieldRow('', '');
  });

  document.getElementById('btn-save-device-settings').addEventListener('click', saveCurrentDeviceSettings);
}

function addCustomFieldRow(key = '', val = '') {
  const container = document.getElementById('custom-fields-container');
  const row = document.createElement('div');
  row.className = 'custom-field-row';
  row.innerHTML = `
    <input type="text" class="cf-key" placeholder="Field name (e.g. stream_port, gpu, os)" value="${escapeHtml(key)}" />
    <input type="text" class="cf-val" placeholder="Field value" value="${escapeHtml(val)}" />
    <button type="button" class="btn-remove-cf" title="Remove field">&times;</button>
  `;

  row.querySelector('.btn-remove-cf').addEventListener('click', () => row.remove());
  container.appendChild(row);
}

function openInspector(dev) {
  if (!dev) return;
  state.selectedDevice = dev;

  const drawer = document.getElementById('inspector-drawer');
  const backdrop = document.getElementById('drawer-backdrop');

  document.getElementById('drawer-avatar').textContent = ICONS[dev.category] || '⚙️';
  document.getElementById('drawer-name').textContent = dev.name || dev.ip;
  document.getElementById('drawer-category').textContent = (dev.category || 'device').toUpperCase();

  const userS = dev.user_settings || {};
  
  document.getElementById('dev-input-alias').value = userS.alias || '';
  document.getElementById('dev-input-ipres').value = userS.ip_reservation || '';
  document.getElementById('dev-input-notes').value = userS.notes || '';

  populateSelect('dev-select-role', state.devicePresets.roles || [], userS.role || '');
  populateSelect('dev-select-location', state.devicePresets.locations || [], userS.location || '');
  populateSelect('dev-select-priority', state.devicePresets.priorities || [], userS.priority || '');
  populateSelect('dev-select-segment', state.devicePresets.segments || [], userS.network_segment || '');

  const cfContainer = document.getElementById('custom-fields-container');
  cfContainer.innerHTML = '';
  const customFields = userS.custom_fields || {};
  for (const [k, v] of Object.entries(customFields)) {
    addCustomFieldRow(k, v);
  }

  document.getElementById('drawer-vendor').textContent = dev.vendor || 'Unknown';
  document.getElementById('drawer-model').textContent = dev.model || dev.description || '-';
  document.getElementById('drawer-firmware').textContent = dev.firmware || 'N/A';
  document.getElementById('drawer-role').textContent = dev.is_gateway ? 'Primary Gateway Router' : (dev.is_extender ? 'Mesh Extender' : (dev.is_local_host ? 'Local Workstation' : (dev.category === 'camera' ? 'CCTV Security Camera' : (dev.category === 'nvr' ? 'Network Video Recorder' : 'LAN Client'))));

  document.getElementById('drawer-ip').textContent = dev.ip || '-';
  document.getElementById('drawer-mac').textContent = dev.mac || '-';
  document.getElementById('drawer-ping').textContent = dev.latency ? `${dev.latency.toFixed(1)} ms` : 'Active';

  const portsContainer = document.getElementById('drawer-ports');
  portsContainer.innerHTML = '';
  const openPorts = dev.open_ports || [];
  if (openPorts.length > 0) {
    openPorts.forEach(p => {
      const span = document.createElement('span');
      const isCam = [554, 8554, 8000, 37777, 8899, 7443].includes(p);
      span.className = `port-tag ${isCam ? 'cam' : ''}`;
      let label = `Port ${p}`;
      if (p === 554 || p === 8554) label = `Port ${p} (RTSP Stream)`;
      if (p === 8000) label = `Port ${p} (NVR / Media)`;
      if (p === 37777) label = `Port ${p} (Dahua NVR)`;
      if (p === 8899) label = `Port ${p} (ONVIF)`;
      span.textContent = label;
      portsContainer.appendChild(span);
    });
  } else {
    portsContainer.innerHTML = '<span style="font-size:0.75rem;color:var(--text-muted)">No open ports discovered</span>';
  }

  const featuresSec = document.getElementById('drawer-features-sec');
  const featuresList = document.getElementById('drawer-features');
  featuresList.innerHTML = '';
  const features = dev.specs?.features || [];
  if (features.length > 0) {
    featuresSec.style.display = 'block';
    features.forEach(f => {
      const li = document.createElement('li');
      li.textContent = f;
      featuresList.appendChild(li);
    });
  } else {
    featuresSec.style.display = 'none';
  }

  const actions = document.getElementById('drawer-actions');
  actions.innerHTML = '';

  if (dev.is_gateway) {
    const btnAdmin = document.createElement('a');
    btnAdmin.href = dev.specs?.default_admin_url || 'https://192.168.0.1';
    btnAdmin.target = '_blank';
    btnAdmin.className = 'btn btn-primary';
    btnAdmin.textContent = 'Open Archer BE550 Web GUI';
    actions.appendChild(btnAdmin);
  }

  if (dev.is_extender) {
    const btnExt = document.createElement('a');
    btnExt.href = dev.specs?.default_admin_url || 'http://192.168.0.76';
    btnExt.target = '_blank';
    btnExt.className = 'btn btn-primary';
    btnExt.textContent = 'Open Netgear Extender Portal';
    actions.appendChild(btnExt);
  }

  if (dev.category === 'camera' || (dev.open_ports && dev.open_ports.includes(554))) {
    const btnRtsp = document.createElement('button');
    btnRtsp.className = 'btn btn-primary';
    btnRtsp.textContent = 'Copy RTSP Stream URL';
    btnRtsp.onclick = () => {
      copyText(`rtsp://admin:password@${dev.ip}:554/stream`);
    };
    actions.appendChild(btnRtsp);

    const btnTestRtsp = document.createElement('button');
    btnTestRtsp.className = 'btn btn-secondary';
    btnTestRtsp.textContent = '🎥 Test RTSP Stream';
    btnTestRtsp.onclick = async () => {
      btnTestRtsp.textContent = 'Testing...';
      try {
        const res = await fetch('/api/camera/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ host: dev.ip, port: 554 })
        });
        const d = await res.json();
        if (d.success) {
          showToast(`RTSP Stream reachable (${d.latency_ms} ms)`, 'success');
          btnTestRtsp.textContent = `🎥 Stream OK (${d.latency_ms}ms)`;
        } else {
          showToast(`RTSP test failed: ${d.error || 'Unreachable'}`, 'error');
          btnTestRtsp.textContent = '🎥 Stream Failed';
        }
      } catch (e) {
        showToast(`RTSP test failed: ${e.message}`, 'error');
        btnTestRtsp.textContent = '🎥 Test RTSP Stream';
      }
    };
    actions.appendChild(btnTestRtsp);

    const btnTvpc = document.createElement('button');
    btnTvpc.className = 'btn btn-secondary';
    btnTvpc.textContent = '📺 Add to tvpc (cameras.conf)';
    btnTvpc.onclick = async () => {
      const name = dev.user_settings?.alias || dev.name || `Camera-${dev.ip}`;
      const url = `rtsp://admin:admin@${dev.ip}:554/live/ch0`;
      try {
        const res = await fetch('/api/camera/add-tvpc', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, url, group: 'Security' })
        });
        const d = await res.json();
        if (d.success) {
          showToast(`Synced "${name}" to ~/.config/tvpc/cameras.conf`, 'success');
        } else {
          showToast(`tvpc sync failed: ${d.error}`, 'error');
        }
      } catch (e) {
        showToast(`tvpc sync failed: ${e.message}`, 'error');
      }
    };
    actions.appendChild(btnTvpc);
  }

  // Wake-on-LAN for non-gateway devices with MAC address
  if (dev.mac && !dev.is_gateway) {
    const btnWol = document.createElement('button');
    btnWol.className = 'btn btn-secondary';
    btnWol.textContent = '⚡ Wake Machine (WoL)';
    btnWol.onclick = async () => {
      btnWol.textContent = 'Sending Magic Packet...';
      try {
        const res = await fetch('/api/devices/wol', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mac: dev.mac })
        });
        const d = await res.json();
        if (d.success) {
          showToast(`Wake-on-LAN packet transmitted to ${dev.mac}`, 'success');
          btnWol.textContent = '⚡ Magic Packet Sent';
        } else {
          showToast(`WoL failed: ${d.error}`, 'error');
          btnWol.textContent = '⚡ Wake Machine (WoL)';
        }
      } catch (e) {
        showToast(`WoL failed: ${e.message}`, 'error');
        btnWol.textContent = '⚡ Wake Machine (WoL)';
      }
    };
    actions.appendChild(btnWol);
  }

  // Open Web GUI shortcut if HTTP/HTTPS ports are open
  const openPortsList = dev.open_ports || [];
  if ((openPortsList.includes(80) || openPortsList.includes(443) || openPortsList.includes(8080) || openPortsList.includes(8443)) && !dev.is_gateway && !dev.is_extender) {
    const p = (openPortsList.includes(443) || openPortsList.includes(8443)) ? (openPortsList.includes(443) ? 443 : 8443) : (openPortsList.includes(80) ? 80 : 8080);
    const proto = (p === 443 || p === 8443) ? 'https' : 'http';
    const btnWeb = document.createElement('a');
    btnWeb.href = `${proto}://${dev.ip}:${p}`;
    btnWeb.target = '_blank';
    btnWeb.className = 'btn btn-secondary';
    btnWeb.textContent = `🌐 Open Web GUI (Port ${p})`;
    actions.appendChild(btnWeb);
  }

  const btnPing = document.createElement('button');
  btnPing.className = 'btn btn-secondary';
  btnPing.textContent = 'Ping This Device';
  btnPing.onclick = async () => {
    btnPing.textContent = 'Pinging...';
    const res = await fetch('/api/ping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ host: dev.ip })
    });
    const data = await res.json();
    btnPing.textContent = data.reachable ? `Ping: ${data.avg?.toFixed(1)} ms` : 'Unreachable';
  };
  actions.appendChild(btnPing);

  drawer.classList.add('open');
  backdrop.classList.add('open');
}

function populateSelect(elemId, options, selectedValue) {
  const sel = document.getElementById(elemId);
  if (!sel) return;
  sel.innerHTML = '<option value="">-- Select or Default --</option>';
  options.forEach(opt => {
    const o = document.createElement('option');
    o.value = opt;
    o.textContent = opt;
    if (opt === selectedValue) o.selected = true;
    sel.appendChild(o);
  });
}

async function saveCurrentDeviceSettings() {
  const dev = state.selectedDevice;
  if (!dev) return;

  const ident = dev.mac || dev.ip;
  if (!ident) return;

  const btn = document.getElementById('btn-save-device-settings');
  btn.disabled = true;
  btn.textContent = "Saving...";

  const alias = document.getElementById('dev-input-alias').value.trim();
  const role = document.getElementById('dev-select-role').value;
  const location = document.getElementById('dev-select-location').value;
  const priority = document.getElementById('dev-select-priority').value;
  const network_segment = document.getElementById('dev-select-segment').value;
  const ip_reservation = document.getElementById('dev-input-ipres').value.trim();
  const notes = document.getElementById('dev-input-notes').value.trim();

  const custom_fields = {};
  document.querySelectorAll('.custom-field-row').forEach(row => {
    const k = row.querySelector('.cf-key').value.trim();
    const v = row.querySelector('.cf-val').value.trim();
    if (k) custom_fields[k] = v;
  });

  const settingsData = {
    alias,
    role,
    location,
    priority,
    network_segment,
    ip_reservation,
    notes,
    custom_fields
  };

  try {
    const res = await fetch('/api/devices/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        identifier: ident,
        profile_id: state.viewingProfileId || state.activeProfileId,
        settings: settingsData
      })
    });
    const result = await res.json();

    if (result.success) {
      dev.user_settings = settingsData;
      if (alias) {
        dev.original_name = dev.original_name || dev.name;
        dev.name = alias;
      }
      document.getElementById('drawer-name').textContent = dev.name;
      
      if (state.topology) {
        renderTopology(state.topology);
        renderDeviceTable(state.topology.devices || []);
      }
      showToast(`Saved settings for ${dev.name || dev.ip}! AI context updated.`, "success");
    } else {
      showToast("Error saving device settings", "error");
    }
  } catch (err) {
    showToast(`Failed to save: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg> Save Device Settings & Update AI Context`;
  }
}

// -------------------------------------------------------------
// 7. ROUTER & MODEM SETTINGS VIEW
// -------------------------------------------------------------
function renderRouterSettings(settings) {
  if (!settings) return;

  const hwTable = document.getElementById('table-router-hw');
  if (hwTable && settings.hardware) {
    hwTable.innerHTML = '';
    const rows = [
      { k: 'Model Name', v: settings.hardware.model_name },
      { k: 'Model ID', v: settings.hardware.model_id },
      { k: 'Vendor', v: settings.hardware.vendor },
      { k: 'Firmware Version', v: settings.hardware.firmware_version },
      { k: 'Build Date', v: settings.hardware.build_date },
      { k: 'Architecture', v: settings.hardware.architecture },
      { k: 'Physical Ethernet', v: settings.hardware.ethernet_ports },
      { k: 'USB Interface', v: settings.hardware.usb_ports }
    ];
    rows.forEach(r => {
      hwTable.innerHTML += `<div class="specs-row"><span class="specs-row-k">${r.k}</span><span class="specs-row-v">${r.v}</span></div>`;
    });
  }

  const lanTable = document.getElementById('table-router-lan');
  if (lanTable && settings.lan_settings) {
    lanTable.innerHTML = '';
    const rows = [
      { k: 'Gateway IPv4', v: settings.lan_settings.gateway_ip },
      { k: 'Subnet Mask', v: settings.lan_settings.subnet_mask },
      { k: 'DHCP Pool', v: settings.lan_settings.dhcp_server },
      { k: 'DNS Servers', v: (settings.lan_settings.dns_servers || []).join(', ') },
      { k: 'MTU Packet Size', v: settings.lan_settings.mtu },
      { k: 'Admin Web Interface', v: settings.lan_settings.admin_web_url },
      { k: 'UPnP Protocol', v: settings.lan_settings.upnp_enabled ? 'Active / Enabled' : 'Disabled' }
    ];
    rows.forEach(r => {
      lanTable.innerHTML += `<div class="specs-row"><span class="specs-row-k">${r.k}</span><span class="specs-row-v">${r.v}</span></div>`;
    });
  }

  const wifiTable = document.getElementById('table-router-wifi');
  if (wifiTable && settings.wifi_settings) {
    wifiTable.innerHTML = '';
    const rows = [
      { k: 'Primary SSID', v: settings.wifi_settings.ssid },
      { k: 'Active BSSID', v: settings.wifi_settings.bssid },
      { k: 'Connected Band', v: settings.wifi_settings.active_band },
      { k: 'Tri-Band Capability', v: (settings.wifi_settings.supported_bands || []).join(' | ') },
      { k: 'Security Protocol', v: settings.wifi_settings.security },
      { k: 'Current PHY Rate', v: settings.wifi_settings.link_rate },
      { k: 'Signal Quality', v: settings.wifi_settings.signal_strength },
      { k: '6GHz Channel Width', v: settings.wifi_settings.channel_width_6ghz }
    ];
    rows.forEach(r => {
      wifiTable.innerHTML += `<div class="specs-row"><span class="specs-row-k">${r.k}</span><span class="specs-row-v">${r.v}</span></div>`;
    });
  }

  const wanTable = document.getElementById('table-router-wan');
  if (wanTable && settings.wan_modem_settings) {
    wanTable.innerHTML = '';
    const rows = [
      { k: 'ISP Provider', v: settings.wan_modem_settings.isp },
      { k: 'Autonomous System', v: settings.wan_modem_settings.asn },
      { k: 'Location / Node', v: settings.wan_modem_settings.location },
      { k: 'NBN Connection', v: settings.wan_modem_settings.connection_type },
      { k: 'Modem Terminal', v: settings.wan_modem_settings.modem_hardware },
      { k: 'Router WAN Port', v: settings.wan_modem_settings.wan_interface },
      { k: 'Public IP', v: settings.wan_modem_settings.wan_ip_detected },
      { k: 'CGNAT Status', v: settings.wan_modem_settings.cgnat_hop_ip },
      { k: 'CGNAT Removal', v: settings.wan_modem_settings.cgnat_opt_out_available }
    ];
    rows.forEach(r => {
      wanTable.innerHTML += `<div class="specs-row"><span class="specs-row-k">${r.k}</span><span class="specs-row-v">${r.v}</span></div>`;
    });
  }

  const pathsGrid = document.getElementById('grid-router-paths');
  if (pathsGrid && settings.admin_navigation_paths) {
    pathsGrid.innerHTML = '';
    for (const [key, val] of Object.entries(settings.admin_navigation_paths)) {
      const cleanKey = key.replace(/_/g, ' ');
      pathsGrid.innerHTML += `
        <div class="nav-path-box">
          <span class="nav-path-title">${cleanKey}</span>
          <span class="nav-path-val">${val}</span>
        </div>
      `;
    }
  }

  if (state.topology && state.topology.router_audit) {
    renderRouterAudit(state.topology.router_audit);
  }
}

// -------------------------------------------------------------
// Router Audit & Login Controller
// -------------------------------------------------------------
function initRouterAudit() {
  const btnLogin = document.getElementById('btn-router-login');
  const btnPwdToggle = document.getElementById('btn-toggle-router-pwd');
  const pwdInput = document.getElementById('router-login-password');
  const btnClearCreds = document.getElementById('btn-clear-saved-creds');
  const btnReaudit = document.getElementById('btn-reaudit-router');
  const btnLogout = document.getElementById('btn-router-logout');
  const btnBannerAudit = document.getElementById('btn-banner-router-audit');

  if (btnPwdToggle && pwdInput) {
    btnPwdToggle.addEventListener('click', () => {
      if (pwdInput.type === 'password') {
        pwdInput.type = 'text';
        btnPwdToggle.textContent = '🔒';
      } else {
        pwdInput.type = 'password';
        btnPwdToggle.textContent = '👁️';
      }
    });
  }

  if (btnLogin) {
    btnLogin.addEventListener('click', () => loginAndAuditRouter());
  }

  if (pwdInput) {
    pwdInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        loginAndAuditRouter();
      }
    });
  }

  if (btnReaudit) {
    btnReaudit.addEventListener('click', () => loginAndAuditRouter());
  }

  if (btnLogout) {
    btnLogout.addEventListener('click', () => logoutRouter());
  }

  if (btnClearCreds) {
    btnClearCreds.addEventListener('click', () => clearSavedRouterCredentials());
  }

  if (btnBannerAudit) {
    btnBannerAudit.addEventListener('click', () => {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      const tabBtn = document.querySelector('.nav-tab[data-tab="router-settings"]');
      if (tabBtn) tabBtn.classList.add('active');
      const tabContent = document.getElementById('tab-router-settings');
      if (tabContent) tabContent.classList.add('active');
      state.activeTab = 'router-settings';
      const pwd = document.getElementById('router-login-password');
      if (pwd) pwd.focus();
    });
  }
}

async function fetchRouterAuditStatus() {
  try {
    const res = await fetch('/api/router/audit');
    if (!res.ok) return;
    const data = await res.json();
    
    const urlInput = document.getElementById('router-login-url');
    const userInput = document.getElementById('router-login-username');
    const pwdInput = document.getElementById('router-login-password');
    const btnClearCreds = document.getElementById('btn-clear-saved-creds');
    const authBadge = document.getElementById('audit-auth-status-badge');

    if (urlInput && data.gateway_url) {
      urlInput.value = data.gateway_url;
    }
    if (userInput && data.saved_username) {
      userInput.value = data.saved_username;
    }
    if (pwdInput && data.has_saved_creds) {
      pwdInput.placeholder = 'Saved router password active';
    }
    if (btnClearCreds) {
      btnClearCreds.style.display = data.has_saved_creds ? 'inline-block' : 'none';
    }
    if (authBadge) {
      if (data.authenticated) {
        authBadge.className = 'badge emerald';
        authBadge.textContent = 'Authenticated (Session Active)';
      } else if (data.has_audit) {
        authBadge.className = 'badge blue';
        authBadge.textContent = 'Audited';
      } else {
        authBadge.className = 'badge';
        authBadge.textContent = 'Not Authenticated';
      }
    }

    if (data.has_audit && data.audit) {
      renderRouterAudit(data.audit);
    }
  } catch (err) {
    console.error('Failed to fetch router audit status:', err);
  }
}

async function loginAndAuditRouter() {
  const urlInput = document.getElementById('router-login-url');
  const userInput = document.getElementById('router-login-username');
  const pwdInput = document.getElementById('router-login-password');
  const rememberInput = document.getElementById('router-login-remember');
  const btnLogin = document.getElementById('btn-router-login');
  const btnText = document.getElementById('btn-router-login-text');
  const msgEl = document.getElementById('router-login-msg');

  const url = urlInput ? urlInput.value.trim() : 'https://192.168.0.1';
  const username = userInput ? userInput.value.trim() : 'admin';
  const password = pwdInput ? pwdInput.value : '';
  const remember = rememberInput ? rememberInput.checked : true;

  if (msgEl) {
    msgEl.className = 'login-feedback-msg';
    msgEl.textContent = '';
  }

  if (!password && (!pwdInput || !pwdInput.placeholder.includes('Saved'))) {
    if (msgEl) {
      msgEl.className = 'login-feedback-msg error';
      msgEl.textContent = 'Please enter router password';
    }
    if (pwdInput) pwdInput.focus();
    return;
  }

  if (btnLogin) btnLogin.disabled = true;
  if (btnText) btnText.textContent = 'Authenticating & Auditing...';

  try {
    const res = await fetch('/api/router/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, username, password, remember })
    });

    const data = await res.json();

    if (res.ok && data.success) {
      showToast('Router logged in & settings audited successfully!', 'success');
      if (msgEl) {
        msgEl.className = 'login-feedback-msg success';
        msgEl.textContent = '✓ Authenticated successfully';
      }
      const authBadge = document.getElementById('audit-auth-status-badge');
      if (authBadge) {
        authBadge.className = 'badge emerald';
        authBadge.textContent = 'Authenticated (Session Active)';
      }
      const btnClearCreds = document.getElementById('btn-clear-saved-creds');
      if (btnClearCreds && remember) {
        btnClearCreds.style.display = 'inline-block';
      }
      if (pwdInput) {
        pwdInput.value = '';
        pwdInput.placeholder = 'Saved router password active';
      }
      renderRouterAudit(data.audit, data.settings);

      // Refresh suggestions tab counter and content
      if (state.topology) {
        state.topology.router_audit = data.audit;
        const sugRes = await fetch('/api/suggestions');
        if (sugRes.ok) {
          const sugData = await sugRes.json();
          state.topology.suggestions = sugData.suggestions;
          renderSuggestions(sugData.suggestions);
          const sugBadge = document.getElementById('sug-badge');
          if (sugBadge) sugBadge.textContent = sugData.suggestions.length;
        }
      }
    } else {
      let errMsg = data.error || 'Login failed';
      if (data.attempts_remaining !== undefined) {
        errMsg += ` (${data.attempts_remaining} attempts remaining before lockout)`;
      }
      showToast(errMsg, 'error');
      if (msgEl) {
        msgEl.className = 'login-feedback-msg error';
        msgEl.textContent = `✕ ${errMsg}`;
      }
    }
  } catch (err) {
    showToast(`Connection error: ${err.message}`, 'error');
    if (msgEl) {
      msgEl.className = 'login-feedback-msg error';
      msgEl.textContent = `✕ Error: ${err.message}`;
    }
  } finally {
    if (btnLogin) btnLogin.disabled = false;
    if (btnText) btnText.textContent = 'Login & Audit Settings';
  }
}

async function logoutRouter() {
  try {
    await fetch('/api/router/logout', { method: 'POST' });
    showToast('Logged out from router', 'info');
    const authBadge = document.getElementById('audit-auth-status-badge');
    if (authBadge) {
      authBadge.className = 'badge';
      authBadge.textContent = 'Not Authenticated';
    }
    const msgEl = document.getElementById('router-login-msg');
    if (msgEl) {
      msgEl.className = 'login-feedback-msg';
      msgEl.textContent = 'Session ended';
    }
  } catch (err) {
    console.error('Logout error:', err);
  }
}

async function clearSavedRouterCredentials() {
  if (!confirm('Clear saved router credentials from this machine?')) return;
  try {
    await fetch('/api/router/credentials/clear', { method: 'POST' });
    showToast('Stored credentials cleared', 'info');
    const pwdInput = document.getElementById('router-login-password');
    if (pwdInput) {
      pwdInput.value = '';
      pwdInput.placeholder = 'Enter router admin password...';
    }
    const btnClearCreds = document.getElementById('btn-clear-saved-creds');
    if (btnClearCreds) btnClearCreds.style.display = 'none';
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

function renderRouterAudit(audit, settings) {
  const dashboard = document.getElementById('router-audit-dashboard');
  if (!dashboard || !audit) return;
  dashboard.style.display = 'block';

  // Health Score and Grade
  const scoreVal = document.getElementById('health-score-val');
  const gradeVal = document.getElementById('health-grade-val');
  const scoreCircle = document.getElementById('health-score-circle');

  const score = audit.health_score ?? 100;
  if (scoreVal) scoreVal.textContent = score;
  if (gradeVal) gradeVal.textContent = `Grade ${audit.grade || 'A'}`;

  if (scoreCircle) {
    scoreCircle.className = 'health-score-circle';
    if (score >= 90) scoreCircle.classList.add('score-excellent');
    else if (score >= 80) scoreCircle.classList.add('score-good');
    else if (score >= 65) scoreCircle.classList.add('score-warning');
    else scoreCircle.classList.add('score-critical');
  }

  // Pill counts
  const pCrit = document.getElementById('pill-audit-critical');
  const pWarn = document.getElementById('pill-audit-warning');
  const pRec = document.getElementById('pill-audit-recommended');
  const pOpt = document.getElementById('pill-audit-opt');

  if (pCrit) pCrit.textContent = `${audit.critical_count || 0} Critical`;
  if (pWarn) pWarn.textContent = `${audit.warning_count || 0} Warnings`;
  if (pRec) pRec.textContent = `${audit.recommended_count || 0} Recommended`;
  if (pOpt) pOpt.textContent = `${audit.optimization_count || 0} Optimizations`;

  // Findings list
  const container = document.getElementById('audit-findings-list');
  if (!container) return;
  container.innerHTML = '';

  const findings = audit.findings || [];
  if (findings.length === 0) {
    container.innerHTML = `
      <div class="solution-placeholder" style="grid-column: 1 / -1;">
        <div class="placeholder-icon">✓</div>
        <h4>All Router Settings Optimized!</h4>
        <p>No critical security risks, Wi-Fi bottlenecks, or misconfigurations were detected.</p>
      </div>
    `;
    return;
  }

  findings.forEach(f => {
    const card = document.createElement('div');
    card.className = `audit-finding-card severity-${f.severity || 'recommended'}`;
    card.innerHTML = `
      <div>
        <div class="finding-top">
          <div>
            <div class="finding-title">${escapeHtml(f.title)}</div>
            <div class="finding-category">${escapeHtml(f.category || 'General')}</div>
          </div>
          <span class="badge ${f.severity === 'critical' ? 'red' : f.severity === 'warning' ? 'amber' : 'blue'}">${escapeHtml(f.badge || f.severity)}</span>
        </div>
        <p class="finding-desc">${escapeHtml(f.description)}</p>
        <div class="finding-vals">
          <div class="finding-val-box">
            <span>CURRENT VALUE</span>
            <strong>${escapeHtml(f.current_value)}</strong>
          </div>
          <div class="finding-val-box">
            <span>RECOMMENDED VALUE</span>
            <strong>${escapeHtml(f.recommended_value)}</strong>
          </div>
        </div>
        <div class="finding-path">
          📍 Click Path: ${escapeHtml(f.router_path)}
        </div>
      </div>
      <div class="finding-actions">
        <button type="button" class="btn btn-sm btn-primary btn-ai-guide" data-prompt="${escapeHtml(f.ai_prompt || f.title)}">
          🤖 Ask AI to Guide Me
        </button>
      </div>
    `;

    const btnAi = card.querySelector('.btn-ai-guide');
    if (btnAi) {
      btnAi.addEventListener('click', () => {
        const prompt = btnAi.getAttribute('data-prompt');
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        const tabBtn = document.querySelector('.nav-tab[data-tab="solver"]');
        if (tabBtn) tabBtn.classList.add('active');
        const tabContent = document.getElementById('tab-solver');
        if (tabContent) tabContent.classList.add('active');
        state.activeTab = 'solver';

        const goalInput = document.getElementById('goal-input');
        if (goalInput) {
          goalInput.value = prompt;
          goalInput.focus();
        }
        const btnSubmit = document.getElementById('btn-submit-goal');
        if (btnSubmit) btnSubmit.click();
      });
    }

    container.appendChild(card);
  });
}

// -------------------------------------------------------------
// 8. DIAGNOSTICS VIEW
// -------------------------------------------------------------
function initDiagnostics() {
  document.getElementById('btn-refresh-metrics').addEventListener('click', async () => {
    showToast("Pinging gateway, CGNAT, and DNS hops...", "info");
    const res = await fetch('/api/metrics');
    const metrics = await res.json();
    renderMetrics(metrics);
    showToast("Metrics updated", "success");
  });

  document.getElementById('btn-run-portscan').addEventListener('click', async () => {
    const ip = document.getElementById('scan-target-ip').value.trim();
    if (!ip) return;
    const resEl = document.getElementById('portscan-results');
    resEl.textContent = `Scanning ports on ${ip}...`;
    try {
      const res = await fetch('/api/portscan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip })
      });
      const data = await res.json();
      if (data.open_ports && data.open_ports.length > 0) {
        resEl.innerHTML = `Open ports on <strong>${ip}</strong>: ${data.open_ports.map(p => `<span class="port-tag">${p}</span>`).join(' ')}`;
      } else {
        resEl.textContent = `No common ports open on ${ip}.`;
      }
    } catch (err) {
      resEl.textContent = `Scan failed: ${err.message}`;
    }
  });

  // Bufferbloat runner
  const btnBb = document.getElementById('btn-run-bufferbloat');
  if (btnBb) {
    btnBb.addEventListener('click', runBufferbloatTest);
  }

  // Spectrum runner and band tabs
  const btnSpec = document.getElementById('btn-scan-spectrum');
  if (btnSpec) {
    btnSpec.addEventListener('click', () => loadWifiSpectrumSurvey('5GHz'));
  }

  document.querySelectorAll('.spectrum-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.spectrum-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const band = tab.getAttribute('data-band');
      if (state.spectrumData) {
        renderSpectrumBand(state.spectrumData, band);
      } else {
        loadWifiSpectrumSurvey(band);
      }
    });
  });
}

async function runBufferbloatTest() {
  const btn = document.getElementById('btn-run-bufferbloat');
  const container = document.getElementById('bufferbloat-results');
  if (!btn || !container) return;

  btn.disabled = true;
  btn.textContent = 'Benchmarking...';
  container.innerHTML = `
    <div class="bb-testing-state">
      <div class="spinner-sm" style="display:inline-block;margin-right:8px;"></div>
      <span>Generating concurrent network load and measuring latency spikes...</span>
    </div>
  `;

  try {
    const res = await fetch('/api/diagnostics/bufferbloat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: '1.1.1.1' })
    });
    const data = await res.json();
    renderBufferbloatResults(data);
    showToast(`Bufferbloat benchmark complete: Grade ${data.grade}`, 'success');
  } catch (err) {
    container.innerHTML = `<div class="text-danger" style="padding:10px;">Benchmark failed: ${escapeHtml(err.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run Test';
  }
}

function renderBufferbloatResults(data) {
  const container = document.getElementById('bufferbloat-results');
  if (!container) return;

  const gradeColors = {
    'A+': 'emerald',
    'A': 'green',
    'B': 'blue',
    'C': 'amber',
    'D': 'orange',
    'F': 'red'
  };
  const colorClass = gradeColors[data.grade] || 'blue';
  const idleMs = data.idle_ping_ms || 0;
  const loadedMs = data.loaded_ping_ms || 0;
  const deltaMs = data.delta_ms || 0;
  const maxBar = Math.max(loadedMs * 1.25, 50);
  const idlePct = Math.min(100, Math.max(4, (idleMs / maxBar) * 100));
  const loadedPct = Math.min(100, Math.max(4, (loadedMs / maxBar) * 100));

  container.innerHTML = `
    <div class="bb-result-card">
      <div class="bb-header-row">
        <div class="bb-grade-box ${colorClass}">
          <span class="bb-grade-letter">${data.grade}</span>
          <span class="bb-grade-sub">BUFFERBLOAT</span>
        </div>
        <div class="bb-meta">
          <div class="bb-summary-title">${escapeHtml(data.grade_description || '')}</div>
          <div class="bb-metrics-row">
            <span class="bb-metric">Idle: <strong>${idleMs.toFixed(1)} ms</strong></span>
            <span class="bb-metric-sep">→</span>
            <span class="bb-metric">Loaded: <strong>${loadedMs.toFixed(1)} ms</strong></span>
            <span class="bb-metric-delta">+${deltaMs.toFixed(1)} ms queue delay</span>
          </div>
          <!-- Visual latency bar comparison -->
          <div style="display:flex;flex-direction:column;gap:5px;margin-top:8px;">
            <div style="display:flex;align-items:center;gap:8px;font-size:0.72rem;">
              <span style="width:70px;color:var(--text-muted);font-weight:600;">Idle Ping:</span>
              <div style="flex:1;height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden;">
                <div style="width:${idlePct}%;height:100%;background:var(--accent-green);border-radius:3px;box-shadow:0 0 6px rgba(158,206,106,0.5);"></div>
              </div>
              <span style="width:55px;text-align:right;font-family:var(--font-mono);font-size:0.72rem;color:var(--text-bright);">${idleMs.toFixed(1)} ms</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;font-size:0.72rem;">
              <span style="width:70px;color:var(--text-muted);font-weight:600;">Under Load:</span>
              <div style="flex:1;height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden;">
                <div style="width:${loadedPct}%;height:100%;background:linear-gradient(90deg, var(--accent-cyan), ${deltaMs > 30 ? 'var(--accent-red)' : 'var(--accent-amber)'});border-radius:3px;"></div>
              </div>
              <span style="width:55px;text-align:right;font-family:var(--font-mono);font-size:0.72rem;color:var(--text-bright);">${loadedMs.toFixed(1)} ms</span>
            </div>
          </div>
        </div>
      </div>
      <div class="bb-recommendation-box">
        <span class="bb-rec-icon">💡</span>
        <span class="bb-rec-text">${escapeHtml(data.recommendation || '')}</span>
      </div>
    </div>
  `;
}

async function loadWifiSpectrumSurvey(activeBand = '5GHz') {
  const btn = document.getElementById('btn-scan-spectrum');
  const container = document.getElementById('spectrum-results');
  if (btn) btn.disabled = true;
  if (container) container.innerHTML = '<div class="spectrum-loading"><div class="spinner-sm" style="display:inline-block;margin-right:8px;"></div>Scanning 2.4 GHz, 5 GHz, and 6 GHz spectrum...</div>';

  try {
    const res = await fetch('/api/diagnostics/spectrum');
    const survey = await res.json();
    state.spectrumData = survey;
    renderSpectrumBand(survey, activeBand);
  } catch (err) {
    if (container) container.innerHTML = `<div class="text-danger" style="padding:10px;">Spectrum scan failed: ${escapeHtml(err.message)}</div>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderSpectrumBand(survey, bandKey = '5GHz') {
  const container = document.getElementById('spectrum-results');
  if (!container || !survey) return;

  const bandData = (survey.bands || {})[bandKey] || { networks: [], channel_counts: {}, recommended_channels: [] };
  const networks = bandData.networks || [];
  const recChannels = bandData.recommended_channels || [];

  if (networks.length === 0) {
    container.innerHTML = `<div class="spectrum-empty">No access points detected on ${bandKey} band.</div>`;
    return;
  }

  const channelCounts = bandData.channel_counts || {};
  let crowdingHtml = '';
  for (const [ch, count] of Object.entries(channelCounts)) {
    crowdingHtml += `
      <div class="spectrum-ch-bar">
        <span class="ch-label">Ch ${ch}</span>
        <div class="ch-track">
          <div class="ch-fill" style="width:${Math.min(count * 35, 100)}%;"></div>
        </div>
        <span class="ch-count">${count} AP${count > 1 ? 's' : ''}</span>
      </div>
    `;
  }

  let apRowsHtml = '';
  networks.forEach(net => {
    const isConn = net.in_use || (net.bssid && net.bssid === survey.connected_bssid);
    apRowsHtml += `
      <div class="spectrum-ap-item ${isConn ? 'connected-ap' : ''}">
        <div class="ap-name-group">
          <span class="ap-ssid">${escapeHtml(net.ssid || '(Hidden)')}</span>
          ${isConn ? '<span class="badge-omarchy" style="font-size:0.65rem;">CONNECTED</span>' : ''}
          <span class="ap-bssid code">${escapeHtml(net.bssid || '')}</span>
        </div>
        <div class="ap-stats-group">
          <span class="ap-ch">Ch ${net.channel}</span>
          <span class="ap-freq">${escapeHtml(net.frequency || '')}</span>
          <span class="ap-sig">${net.signal}%</span>
          <span class="ap-sec">${escapeHtml(net.security || 'Open')}</span>
        </div>
      </div>
    `;
  });

  container.innerHTML = `
    <div class="spectrum-view">
      <div class="spectrum-rec-bar">
        <span class="rec-label">Recommended Clean Channels for Archer BE550:</span>
        <span class="rec-pills">
          ${recChannels.map(c => `<span class="pill-ch">Ch ${c}</span>`).join(' ')}
        </span>
      </div>
      <div class="spectrum-crowding-section">
        <h5>Channel Crowding Analysis (${bandKey})</h5>
        <div class="spectrum-bars-list">
          ${crowdingHtml}
        </div>
      </div>
      <div class="spectrum-ap-section">
        <h5>Nearby Access Points (${networks.length} Detected)</h5>
        <div class="spectrum-ap-list">
          ${apRowsHtml}
        </div>
      </div>
    </div>
  `;
}

function renderDiagnostics(topo) {
  const hopsList = document.getElementById('hops-list');
  hopsList.innerHTML = '';
  (topo.hops || []).forEach(h => {
    const item = document.createElement('div');
    item.className = 'hop-item';
    const tagClass = h.is_cgnat ? 'cgnat' : (h.hop === 1 ? 'gw' : 'core');
    item.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;">
        <span class="hop-num">#${h.hop}</span>
        <span class="hop-ip">${h.ip}</span>
      </div>
      <div style="display:flex;align-items:center;gap:10px;">
        <span class="hop-tag ${tagClass}">${h.label}</span>
        <span class="code" style="color:var(--accent-green);">${h.latency}</span>
      </div>
    `;
    hopsList.appendChild(item);
  });

  renderMetrics(topo.metrics || {});

  const wifiGrid = document.getElementById('wifi-specs-grid');
  wifiGrid.innerHTML = '';
  const host = topo.host || {};
  const wifi = host.wifi || {};
  
  const specs = [
    { k: 'Interface', v: host.interface || 'wlo1' },
    { k: 'IP Address', v: host.ip || '192.168.0.5' },
    { k: 'Connected SSID', v: wifi.ssid || 'BananaFarm' },
    { k: 'Band / Freq', v: `${wifi.frequency || '5180 MHz'} (Ch ${wifi.channel || '36'})` },
    { k: 'Link Rate', v: wifi.rate || '270 Mbit/s' },
    { k: 'Signal Quality', v: wifi.signal || '85%' },
    { k: 'Security Protocol', v: wifi.security || 'WPA2/WPA3' },
    { k: 'Hardware MAC', v: host.mac || '-' }
  ];

  specs.forEach(s => {
    const box = document.createElement('div');
    box.className = 'spec-box';
    box.innerHTML = `
      <div class="spec-box-k">${s.k}</div>
      <div class="spec-box-v">${s.v}</div>
    `;
    wifiGrid.appendChild(box);
  });
}

function generateSparklineSvg(samples, strokeColor = '#10b981', fillColor = 'rgba(16, 185, 129, 0.15)') {
  if (!samples || samples.length < 2) {
    return `<svg class="metric-sparkline-svg" viewBox="0 0 90 22"><line x1="0" y1="11" x2="90" y2="11" stroke="${strokeColor}" stroke-width="1.5" stroke-dasharray="3,3" opacity="0.4"/></svg>`;
  }
  const min = Math.min(...samples);
  const max = Math.max(...samples);
  const range = (max - min) || 1;
  const width = 90;
  const height = 22;
  const padY = 3;
  const usableH = height - padY * 2;

  const points = samples.map((v, i) => {
    const x = (i / (samples.length - 1)) * width;
    const y = padY + (1 - (v - min) / range) * usableH;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const polyline = points.join(' ');
  const areaPoints = `0,${height} ${polyline} ${width},${height}`;
  const gradId = `spark-grad-${Math.floor(Math.random() * 1000000)}`;

  return `
    <svg class="metric-sparkline-svg" viewBox="0 0 ${width} ${height}">
      <defs>
        <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      <polygon points="${areaPoints}" fill="url(#${gradId})" />
      <polyline fill="none" stroke="${strokeColor}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" points="${polyline}" />
      <circle cx="${points[points.length - 1].split(',')[0]}" cy="${points[points.length - 1].split(',')[1]}" r="2.5" fill="${strokeColor}" />
    </svg>
  `;
}

function renderMetrics(metrics) {
  const grid = document.getElementById('metrics-grid');
  if (!grid) return;
  grid.innerHTML = '';

  const targets = [
    { key: 'router', label: 'Gateway Router (BE550)', ip: '192.168.0.1' },
    { key: 'isp_hop', label: 'ISP CGNAT Gateway', ip: '100.91.128.1' },
    { key: 'cloudflare', label: 'Cloudflare DNS', ip: '1.1.1.1' },
    { key: 'google', label: 'Google Public DNS', ip: '8.8.8.8' }
  ];

  targets.forEach(t => {
    const m = (metrics && metrics[t.key]) || {};
    const card = document.createElement('div');
    card.className = 'metric-card';

    let latencyClass = 'offline';
    let latencyBadge = 'OFFLINE';
    let strokeColor = '#64748b';

    if (m.reachable && m.avg !== undefined && m.avg !== null) {
      if (m.avg < 15) {
        latencyClass = 'excellent';
        latencyBadge = 'EXCELLENT';
        strokeColor = '#10b981';
      } else if (m.avg < 50) {
        latencyClass = 'good';
        latencyBadge = 'GOOD';
        strokeColor = '#7dcfff';
      } else if (m.avg < 120) {
        latencyClass = 'moderate';
        latencyBadge = 'MODERATE';
        strokeColor = '#e0af68';
      } else {
        latencyClass = 'high';
        latencyBadge = 'HIGH';
        strokeColor = '#f43f5e';
      }
    }

    const avgVal = (m.avg !== undefined && m.avg !== null)
      ? `${m.avg.toFixed(1)} <span style="font-size: 0.8rem; font-weight: 500; color: var(--text-muted);">ms</span>`
      : (m.reachable ? 'Online' : 'Timeout');
    const jitterText = (m.mdev !== undefined && m.mdev !== null)
      ? `±${m.mdev.toFixed(2)} ms jitter`
      : `${m.loss || 0}% loss`;

    // Synthesize realistic sparkline points from min, avg, max, mdev
    let samples = [];
    if (m.reachable && m.avg !== undefined && m.avg !== null) {
      const min = m.min ?? (m.avg * 0.85);
      const max = m.max ?? (m.avg * 1.2);
      const dev = m.mdev ?? ((max - min) / 3);
      samples = [
        Math.max(0.1, m.avg - dev * 0.4),
        Math.max(0.1, min),
        Math.max(0.1, m.avg + dev * 0.5),
        Math.max(0.1, m.avg - dev * 0.2),
        Math.max(0.1, max),
        Math.max(0.1, m.avg)
      ];
    }

    const sparkSvg = generateSparklineSvg(samples, strokeColor);

    card.innerHTML = `
      <div class="metric-header">
        <div class="metric-label">${t.label}</div>
        <span class="latency-pill ${latencyClass}">${latencyBadge}</span>
      </div>
      <div class="metric-val ${latencyClass === 'high' ? 'danger' : (latencyClass === 'moderate' ? 'warning' : '')}">
        ${avgVal}
      </div>
      <div class="metric-sparkline-row">
        <div class="metric-sub">${t.ip} • ${jitterText}</div>
        ${sparkSvg}
      </div>
    `;
    grid.appendChild(card);
  });
}

// -------------------------------------------------------------
// 9. SETTINGS MODAL (MISTRAL AI, OPENROUTER & LOCAL EXPERT)
// -------------------------------------------------------------
function initSettings() {
  const modal = document.getElementById('modal-settings');
  const openBtn = document.getElementById('btn-settings');
  const closeBtn = document.getElementById('btn-close-settings');
  const saveBtn = document.getElementById('btn-save-settings');

  document.querySelectorAll('.provider-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.provider-toggle-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.provider-panel').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const provider = btn.getAttribute('data-provider');
      const panel = document.getElementById(`panel-${provider}`);
      if (panel) panel.classList.add('active');
    });
  });

  openBtn.addEventListener('click', async () => {
    const mistralSelect = document.getElementById('mistral-model');
    mistralSelect.innerHTML = '';
    (state.models.mistral || []).forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name;
      if (m.id === state.config.mistral_model) opt.selected = true;
      mistralSelect.appendChild(opt);
    });

    const orSelect = document.getElementById('openrouter-model');
    orSelect.innerHTML = '';
    (state.models.openrouter || []).forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name;
      if (m.id === state.config.openrouter_model) opt.selected = true;
      orSelect.appendChild(opt);
    });

    const geminiSelect = document.getElementById('gemini-model');
    if (geminiSelect) {
      geminiSelect.innerHTML = '';
      (state.models.gemini || []).forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = m.name;
        if (m.id === state.config.gemini_model) opt.selected = true;
        geminiSelect.appendChild(opt);
      });
    }

    document.getElementById('mistral-key').value = state.config.mistral_raw_key || '';
    document.getElementById('openrouter-key').value = state.config.openrouter_raw_key || '';
    const gKeyInput = document.getElementById('gemini-key');
    if (gKeyInput) gKeyInput.value = state.config.gemini_raw_key || '';

    const activeProvider = state.config.ai_provider || 'mistral';
    const activeToggle = document.querySelector(`.provider-toggle-btn[data-provider="${activeProvider}"]`);
    if (activeToggle) activeToggle.click();

    modal.classList.add('open');
  });

  closeBtn.addEventListener('click', () => modal.classList.remove('open'));
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.remove('open');
  });

  saveBtn.addEventListener('click', async () => {
    const activeToggle = document.querySelector('.provider-toggle-btn.active');
    const provider = activeToggle ? activeToggle.getAttribute('data-provider') : 'mistral';

    const mistralKey = document.getElementById('mistral-key').value.trim();
    const mistralModel = document.getElementById('mistral-model').value;
    const openrouterKey = document.getElementById('openrouter-key').value.trim();
    const openrouterModel = document.getElementById('openrouter-model').value;
    const geminiKey = document.getElementById('gemini-key')?.value.trim() || '';
    const geminiModel = document.getElementById('gemini-model')?.value || 'gemini-2.0-flash';

    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ai_provider: provider,
        mistral_api_key: mistralKey,
        mistral_model: mistralModel,
        openrouter_api_key: openrouterKey,
        openrouter_model: openrouterModel,
        gemini_api_key: geminiKey,
        gemini_model: geminiModel
      })
    });

    state.config.ai_provider = provider;
    state.config.mistral_has_key = Boolean(mistralKey);
    state.config.mistral_raw_key = mistralKey;
    state.config.mistral_model = mistralModel;
    state.config.openrouter_has_key = Boolean(openrouterKey);
    state.config.openrouter_raw_key = openrouterKey;
    state.config.openrouter_model = openrouterModel;
    state.config.gemini_has_key = Boolean(geminiKey);
    state.config.gemini_raw_key = geminiKey;
    state.config.gemini_model = geminiModel;

    updateEngineBadge();
    modal.classList.remove('open');
    showToast(`AI Engine settings applied: ${provider.toUpperCase()}`, "success");
  });
}

// -------------------------------------------------------------
// Network Profiles Manager
// -------------------------------------------------------------
function initProfiles() {
  const pill = document.getElementById('pill-profile');
  if (pill) {
    pill.addEventListener('click', () => openProfilesModal());
  }

  const closeBtn = document.getElementById('close-profiles-modal');
  const closeBtn2 = document.getElementById('btn-profiles-modal-close');
  const modal = document.getElementById('profiles-modal');
  if (closeBtn) closeBtn.addEventListener('click', () => modal?.classList.remove('open', 'active'));
  if (closeBtn2) closeBtn2.addEventListener('click', () => modal?.classList.remove('open', 'active'));
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('open', 'active');
    });
  }

  const returnLiveBtn = document.getElementById('btn-return-live');
  if (returnLiveBtn) {
    returnLiveBtn.addEventListener('click', () => switchToActiveProfile());
  }
}

async function refreshProfilesList() {
  try {
    const res = await fetch('/api/profiles');
    const data = await res.json();
    state.profiles = data.profiles || [];
    state.activeProfileId = data.active_profile_id;
    if (!state.viewingProfileId) {
      state.viewingProfileId = data.viewing_profile_id || state.activeProfileId;
    }
  } catch (e) {
    console.error("Error refreshing profiles list:", e);
  }
}

async function openProfilesModal() {
  const modal = document.getElementById('profiles-modal');
  if (!modal) return;
  modal.classList.add('open', 'active');
  await refreshProfilesList();
  renderProfilesList();
}

function renderProfilesList() {
  const container = document.getElementById('profiles-list');
  if (!container) return;
  if (!state.profiles || state.profiles.length === 0) {
    container.innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-dim);">No network profiles recorded yet. Perform a scan to create your first profile.</div>`;
    return;
  }

  container.innerHTML = state.profiles.map(p => {
    const isLive = Boolean(state.activeProfileId && p.id === state.activeProfileId);
    const isViewing = Boolean(state.viewingProfileId && p.id === state.viewingProfileId);
    let cardClass = 'profile-card';
    if (isLive) cardClass += ' active';
    if (isViewing && !isLive) cardClass += ' viewing';

    let icon = p.network_type === 'wifi' ? '📶' : '🌐';
    let badgeHtml = '';
    if (isLive && isViewing) {
      badgeHtml = `<span class="profile-badge-tag connected">LIVE & ACTIVE</span>`;
    } else if (isLive) {
      badgeHtml = `<span class="profile-badge-tag connected">CONNECTED LIVE</span>`;
    } else if (isViewing) {
      badgeHtml = `<span class="profile-badge-tag viewing">VIEWING SNAPSHOT</span>`;
    }

    const lastSeenStr = p.last_seen_at ? new Date(p.last_seen_at).toLocaleString() : 'Recently';

    return `
      <div class="${cardClass}" data-profile-id="${p.id}">
        <div class="profile-card-left">
          <div class="profile-card-icon">${icon}</div>
          <div class="profile-card-info">
            <div class="profile-card-title-row">
              <span class="profile-card-name">${escapeHtml(p.name)}</span>
              ${badgeHtml}
            </div>
            <div class="profile-card-meta">
              ${p.ssid ? `<span class="profile-card-meta-item">SSID: <strong>${escapeHtml(p.ssid)}</strong></span>` : ''}
              ${p.bssid ? `<span class="profile-card-meta-item">BSSID: <code>${escapeHtml(p.bssid)}</code></span>` : ''}
              <span class="profile-card-meta-item">Devices: <strong>${p.device_count || 0}</strong></span>
              ${p.gateway ? `<span class="profile-card-meta-item">Gateway: <code>${escapeHtml(p.gateway)}</code></span>` : ''}
              ${p.subnet ? `<span class="profile-card-meta-item">Subnet: <code>${escapeHtml(p.subnet)}</code></span>` : ''}
              <span class="profile-card-meta-item">Last seen: ${lastSeenStr}</span>
            </div>
          </div>
        </div>
        <div class="profile-card-right">
          ${!isViewing ? `<button class="btn-card-action primary" onclick="switchToProfile('${p.id}')">View Map</button>` : `<button class="btn-card-action" disabled style="opacity:0.6;cursor:default;">Active View</button>`}
          <button class="btn-card-action" onclick="promptRenameProfile('${p.id}', '${escapeHtml(p.name)}')">Rename</button>
          ${!isLive ? `<button class="btn-card-action danger" onclick="confirmDeleteProfile('${p.id}', '${escapeHtml(p.name)}')">Delete</button>` : ''}
        </div>
      </div>
    `;
  }).join('');
}

async function switchToProfile(profileId) {
  try {
    const res = await fetch(`/api/profiles/${encodeURIComponent(profileId)}/select`, { method: 'POST' });
    const data = await res.json();
    if (data.success && data.topology) {
      state.viewingProfileId = profileId;
      state.topology = data.topology;
      updateUIWithTopology(state.topology);
      showToast(`Switched to profile: ${data.profile.name || profileId}`, 'info');
      const modal = document.getElementById('profiles-modal');
      if (modal) modal.classList.remove('open', 'active');
    } else {
      showToast(data.error || 'Failed to switch profile', 'error');
    }
  } catch (err) {
    showToast(`Error switching profile: ${err.message}`, 'error');
  }
}

async function switchToActiveProfile() {
  if (state.activeProfileId) {
    await switchToProfile(state.activeProfileId);
  } else {
    await triggerRescan();
  }
}

async function promptRenameProfile(profileId, currentName) {
  const newName = prompt("Enter new profile name:", currentName);
  if (!newName || newName.trim() === currentName) return;
  try {
    const res = await fetch(`/api/profiles/${encodeURIComponent(profileId)}/rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName.trim() })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Profile renamed to: ${data.name}`, 'success');
      await refreshProfilesList();
      renderProfilesList();
      if (state.topology && state.topology.profile && state.topology.profile.id === profileId) {
        state.topology.profile.name = data.name;
        const val = document.getElementById('val-profile');
        if (val) val.textContent = data.name;
        const bannerName = document.getElementById('banner-profile-name');
        if (bannerName) bannerName.textContent = data.name;
      }
    } else {
      showToast(data.error || 'Failed to rename profile', 'error');
    }
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

async function confirmDeleteProfile(profileId, profileName) {
  if (!confirm(`Are you sure you want to delete profile '${profileName}'? Its saved map and device customizations will be removed.`)) return;
  try {
    const res = await fetch(`/api/profiles/${encodeURIComponent(profileId)}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      showToast(`Profile '${profileName}' deleted`, 'success');
      await refreshProfilesList();
      renderProfilesList();
    } else {
      showToast(data.error || 'Failed to delete profile', 'error');
    }
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

window.switchToProfile = switchToProfile;
window.switchToActiveProfile = switchToActiveProfile;
window.promptRenameProfile = promptRenameProfile;
window.confirmDeleteProfile = confirmDeleteProfile;

