// Cathedral MPC Bridge — AnythingLLM Agent Skill (Desktop)
// Runs inside AnythingLLM's Node runtime. No servers. Connects out to HA MPC (ws://.../mcp).
// Provides deterministic .env read/write via MPC config.read/config.write.
// Auto-starts on load so enabling the skill spins up the bridge immediately.

"use strict";

const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const http = require("node:http");
const https = require("node:https");
const crypto = require("node:crypto");

// Try to obtain a WebSocket implementation:
// 1) global WebSocket if present
// 2) 'ws' if the desktop runtime bundles it
let WSImpl = null;
try { WSImpl = (globalThis && globalThis.WebSocket) ? globalThis.WebSocket : require("ws"); } catch {}

// ── CONFIG (single placeholder) ─────────────────────────────────────────────────
const ORCH_URL = "ws://homeassistant.local:5005/mcp"; // exact MPC path
const AUTH = "Bearer <YOUR_LONG_LIVED_TOKEN_HERE>";   // << insert HA token; keep 'Bearer ' prefix
const WORKSPACE = "anythingllm_desktop";
const CLIENT = "anythingllm/agent-skill";
const VERSION = "v1";
const HEARTBEAT_MS = 30000;
// ───────────────────────────────────────────────────────────────────────────────

function log(level, msg) {
  try { console.log(`[Cathedral-MPC-Bridge][${level}] ${msg}`); } catch {}
}

function storageDir() {
  if (process.platform === "win32") {
    const base = process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming");
    return path.join(base, "anythingllm-desktop", "storage");
  } else if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Application Support", "anythingllm-desktop", "storage");
  }
  return path.join(os.homedir(), ".config", "anythingllm-desktop", "storage");
}
const ENV_PATH = path.join(storageDir(), ".env");

function readEnv() {
  try {
    const txt = fs.readFileSync(ENV_PATH, "utf8");
    const out = {};
    for (const line of txt.split(/\r?\n/)) {
      const t = line.trim();
      if (!t || t.startsWith("#")) continue;
      const i = t.indexOf("=");
      if (i <= 0) continue;
      const k = t.slice(0, i).trim();
      let v = t.slice(i + 1).trim();
      if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
      out[k] = v;
    }
    return out;
  } catch { return {}; }
}

function needsQuotes(v) { return /\s|["'#]/.test(v); }

function writeEnvAtomically(map) {
  const header = [
    "# AnythingLLM .env (managed by Cathedral MPC Bridge)",
    `# Last update: ${new Date().toISOString()}`
  ];
  const keys = Object.keys(map).sort((a,b)=>a.localeCompare(b));
  const lines = header.concat(keys.map(k => `${k}=${needsQuotes(map[k] ?? "") ? JSON.stringify(String(map[k] ?? "")) : String(map[k] ?? "")}`));
  const tmp = ENV_PATH + ".tmp";
  fs.writeFileSync(tmp, lines.join(os.EOL), "utf8");
  fs.renameSync(tmp, ENV_PATH);
}

function normalize(map) {
  const norm = k => (map[k] ?? "").toString().trim();
  return {
    LMSTUDIO_BASE_PATH: norm("LMSTUDIO_BASE_PATH"),
    EMBEDDING_BASE_PATH: norm("EMBEDDING_BASE_PATH"),
    CHROMA_URL:          norm("CHROMA_URL"),
    VECTOR_DB:           norm("VECTOR_DB"),
    STORAGE_DIR:         storageDir(),
    orchestrator_upserts_only: true
  };
}

function uid(prefix) { return `${prefix}_${crypto.randomBytes(8).toString("hex")}`; }
function wsSend(ws, obj) { try { ws.send(JSON.stringify(obj)); } catch {} }

async function httpJson(url, timeoutMs) {
  return new Promise((resolve) => {
    try {
      const lib = url.startsWith("https") ? https : http;
      const req = lib.get(url, { timeout: timeoutMs || 3000 }, (res) => {
        if ((res.statusCode || 500) >= 400) { res.resume(); return resolve(null); }
        const chunks = [];
        res.on("data", d => chunks.push(Buffer.isBuffer(d) ? d : Buffer.from(d)));
        res.on("end", () => {
          try { resolve(JSON.parse(Buffer.concat(chunks).toString("utf8"))); }
          catch { resolve(null); }
        });
      });
      req.on("timeout", () => { try { req.destroy(new Error("timeout")); } catch {} });
      req.on("error", () => resolve(null));
    } catch { resolve(null); }
  });
}

function startBridge() {
  if (!WSImpl) { log("error","No WebSocket impl available in this Node runtime."); return; }

  let ws = null;
  let hb = null;
  let backoff = 1000;

  const connect = () => {
    try {
      ws = new WSImpl(ORCH_URL, { headers: { "Authorization": AUTH } });
    } catch (e) {
      log("error", `WebSocket ctor failed: ${e && e.message || e}`); scheduleReconnect(); return;
    }

    ws.onopen = async () => {
      log("info", `Connected to ${ORCH_URL}`);
      backoff = 1000;

      // Handshake
      wsSend(ws, {
        id: uid("hello"),
        type: "mcp.request",
        scope: "handshake",
        headers: {
          authorization: AUTH,
          workspace_id: WORKSPACE,
          client: CLIENT,
          client_version: VERSION
        },
        body: { capabilities: ["config.read","config.write","session.*","memory.*"], orchestrator_upserts_only: true }
      });
      log("info","Handshake sent.");

      // Proactive config.read.result after 2s
      setTimeout(async () => {
        if (!ws || ws.readyState !== 1) return;
        const body = normalize(readEnv());
        try {
          const base = body.LMSTUDIO_BASE_PATH;
          if (base) {
            const u = (base.endsWith("/v1") ? base : (base.replace(/\/+$/,"") + "/v1")) + "/models";
            const data = await httpJson(u, 2500);
            if (data && Array.isArray(data.data)) body.models_count = data.data.length;
          }
        } catch {}
        wsSend(ws, { type: "mcp.event", scope: "config.read.result", headers: { workspace_id: WORKSPACE }, body });
        log("info","Initial config.read.result pushed.");
      }, 2000);

      // Heartbeat
      if (hb) clearInterval(hb);
      hb = setInterval(() => {
        if (ws && ws.readyState === 1) {
          wsSend(ws, { type:"mcp.event", scope:"heartbeat", headers:{ workspace_id: WORKSPACE }, body:{ ts:new Date().toISOString() } });
        }
      }, HEARTBEAT_MS);
    };

    ws.onmessage = (ev) => {
      let msg = null;
      try { msg = JSON.parse(ev.data?.toString?.() ?? ev.data); } catch { return; }
      if (!msg || msg.type !== "mcp.request") return;

      // Handle config.read
      if (msg.scope === "config.read") {
        const body = normalize(readEnv());
        wsSend(ws, { id: msg.id, type: "mcp.response", scope: "config.read", ok: true, body });
        log("info","config.read served.");
        return;
      }

      // Handle config.write
      if (msg.scope === "config.write") {
        try {
          const ALLOW = new Set(["LMSTUDIO_BASE_PATH","EMBEDDING_BASE_PATH","CHROMA_URL","VECTOR_DB"]);
          const updates = msg.body?.updates || {};
          const map = readEnv();
          let changed = false;
          for (const [k,v] of Object.entries(updates)) {
            if (!ALLOW.has(k)) continue;
            if (typeof v !== "string") continue;
            if (map[k] !== v) { map[k] = v; changed = true; }
          }
          if (changed) writeEnvAtomically(map);
          wsSend(ws, { id: msg.id, type: "mcp.response", scope: "config.write", ok: true, body: normalize(map) });
          log("info", `config.write applied: ${Object.keys(updates).join(", ") || "(none)"}`);
        } catch (err) {
          wsSend(ws, { id: msg.id, type: "mcp.response", scope: "config.write", ok: false, error: { code: "WRITE_FAIL", message: err?.message || String(err) } });
          log("error", `config.write failed: ${err?.message || err}`);
        }
        return;
      }

      // Other scopes are handled on the Orchestrator side.
    };

    ws.onclose = () => {
      log("warn","MCP socket closed.");
      if (hb) { clearInterval(hb); hb = null; }
      scheduleReconnect();
    };
    ws.onerror = (err) => { log("error", `WebSocket error: ${err?.message || String(err)}`); };
  };

  function scheduleReconnect() {
    setTimeout(connect, backoff);
    backoff = Math.min(backoff * 2, 30000);
  }

  connect();
}

// Auto-start the bridge on plugin load
try { startBridge(); } catch (e) { log("error", `Bridge init failed: ${e?.message || e}`); }

// AnythingLLM Agent Skill contract: export at least one callable that returns a string.
// These are NO-OP commands used for health/status; the bridge runs automatically on load.
module.exports = {
  status: async () => "[Cathedral-MPC-Bridge] running",
  restart: async () => { startBridge(); return "[Cathedral-MPC-Bridge] restart signal sent"; }
};
