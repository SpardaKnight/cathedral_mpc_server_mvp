"use strict";

/**
 * Cathedral MPC Bridge - AnythingLLM Agent Skill (Desktop)
 * - Opens a persistent WebSocket to the Orchestrator MPC server.
 * - Handles config.read and config.write locally for .env synchronization.
 * - Exposes a minimal agent command surface: configure | connect | restart | status.
 * - Always return a string per AnythingLLM rules.
 */

const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const http = require("node:http");
const https = require("node:https");
const crypto = require("node:crypto");

// Directories
const PLUGIN_DIR = __dirname;
const LOCAL_ENV = path.join(PLUGIN_DIR, ".env");

// AnythingLLM Desktop storage .env (the one we read/write for config.*)
function storageDir() {
  if (process.platform === "win32") {
    const base = process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming");
    return path.join(base, "anythingllm-desktop", "storage");
  } else if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Application Support", "anythingllm-desktop", "storage");
  }
  return path.join(os.homedir(), ".config", "anythingllm-desktop", "storage");
}
const ALLM_STORAGE = storageDir();
const ALLM_ENV_PATH = path.join(ALLM_STORAGE, ".env");

// Logging
function log(level, msg, extra) {
  const base = `[Cathedral-MPC-Bridge][${level}] ${msg}`;
  try { if (extra) console.log(base, extra); else console.log(base); } catch {}
}

// Simple .env helpers
function readEnvFile(file) {
  try {
    const txt = fs.readFileSync(file, "utf8");
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
function quoteIfNeeded(v) { return /\s|["'#]/.test(v) ? `"${String(v).replace(/"/g,'\\"')}"` : String(v); }
function writeEnvAtomically(file, map) {
  const tmp = `${file}.${crypto.randomBytes(6).toString("hex")}.tmp`;
  const lines = Object.entries(map).map(([k, v]) => `${k}=${quoteIfNeeded(v)}`).join(os.EOL);
  fs.writeFileSync(tmp, lines, "utf8");
  fs.renameSync(tmp, file);
}

// Minimal HTTP json fetch for future extensions
async function httpJson(url, timeoutMs) {
  return new Promise((resolve) => {
    try {
      const lib = url.startsWith("https") ? https : http;
      const req = lib.get(url, { timeout: timeoutMs || 3000 }, (res) => {
        if ((res.statusCode || 500) >= 400) { res.resume(); return resolve(null); }
        const chunks = [];
        res.on("data", d => chunks.push(Buffer.isBuffer(d) ? d : Buffer.from(d)));
        res.on("end", () => { try { resolve(JSON.parse(Buffer.concat(chunks).toString("utf8"))); } catch { resolve(null); } });
      });
      req.on("timeout", () => { try { req.destroy(new Error("timeout")); } catch {} });
      req.on("error", () => resolve(null));
    } catch { resolve(null); }
  });
}

// WebSocket impl
let WSImpl = null;
try { WSImpl = (globalThis && globalThis.WebSocket) ? globalThis.WebSocket : require("ws"); } catch {}

let _ws = null;
let _hb = null;
let _reconnectTimer = null;
let _orchUrl = null;
let _auth = null;

const MPC_CAPABILITIES = ["config.read", "config.write", "session.*", "memory.*"];

function wsSend(ws, obj) { try { ws.send(JSON.stringify(obj)); } catch {} }
function uid(prefix) { return `${prefix}_${crypto.randomBytes(8).toString("hex")}`; }

function readAnythingLLMEnv() {
  const env = readEnvFile(ALLM_ENV_PATH);
  return {
    LMSTUDIO_BASE_PATH: env.LMSTUDIO_BASE_PATH || "",
    EMBEDDING_BASE_PATH: env.EMBEDDING_BASE_PATH || "",
    CHROMA_URL: env.CHROMA_URL || "",
    VECTOR_DB: env.VECTOR_DB || "",
    STORAGE_DIR: ALLM_STORAGE,
    orchestrator_upserts_only: true
  };
}

function sendConfigReadResult(ws, correlationId, isError) {
  const body = readAnythingLLMEnv();
  const message = {
    id: correlationId || uid("cfgsync"),
    type: correlationId ? "mcp.response" : "mcp.event",
    scope: "config.read.result",
    ok: !isError,
    body
  };
  wsSend(ws, message);
}

function closeBridge() {
  try { if (_hb) clearInterval(_hb); } catch {}
  _hb = null;
  try { if (_reconnectTimer) clearTimeout(_reconnectTimer); } catch {}
  _reconnectTimer = null;
  try { if (_ws) _ws.close(); } catch {}
  _ws = null;
}

function scheduleReconnect() {
  try { if (_reconnectTimer) clearTimeout(_reconnectTimer); } catch {}
  _reconnectTimer = setTimeout(() => { try { connect(); } catch (e) { log("error", "reconnect failed", e?.message || e); } }, 5000);
}

function currentConfig(params) {
  const local = readEnvFile(LOCAL_ENV);
  const auth = (params?.auth || local.AUTH || process.env.CATHEDRAL_MPC_TOKEN || "").trim();
  const orchUrl = (params?.orch_url || local.ORCH_URL || "ws://homeassistant.local:5005/mcp").trim();
  return { auth, orchUrl };
}

function connect(params) {
  if (!WSImpl) { log("error","No WebSocket implementation available"); return "No WebSocket"; }
  const { auth, orchUrl } = currentConfig(params);
  if (!auth || !auth.toLowerCase().startsWith("bearer ")) return "Missing AUTH 'Bearer <token>' in plugin .env or params";
  _auth = auth;
  _orchUrl = orchUrl;

  closeBridge();

  const ws = new WSImpl(_orchUrl, [], { headers: { authorization: _auth } });
  _ws = ws;

  ws.onopen = async () => {
    log("info", `Connected ${_orchUrl}`);
    // Handshake
    wsSend(ws, {
      id: uid("hello"),
      type: "mcp.request",
      scope: "handshake",
      headers: { authorization: _auth, workspace_id: "anythingllm_desktop", client: "anythingllm/agent-skill", client_version: "v1" },
      body: { capabilities: MPC_CAPABILITIES, orchestrator_upserts_only: true }
    });
    // Push initial config.read.result shortly after connect
    setTimeout(() => {
      try {
        sendConfigReadResult(ws, null, false);
        log("info", "Pushed initial config.read.result");
      } catch (e) {
        log("warn", "Failed to push config.read.result", e?.message || e);
      }
    }, 1500);

    _hb = setInterval(() => { try { wsSend(ws, { id: uid("hb"), type: "mcp.event", scope: "heartbeat", ts: Date.now() }); } catch {} }, 30000);
  };

  ws.onmessage = async (e) => {
    let msg = {};
    try { msg = JSON.parse(String(e?.data || "{}")); } catch {}
    const scope = msg.scope || "";
    if (msg.type !== "mcp.request") return;

    if (scope === "config.read") {
      try {
        sendConfigReadResult(ws, msg.id, false);
      } catch (err) {
        wsSend(ws, { id: msg.id, type: "mcp.response", scope: "config.read.result", ok: false, error: { code: "READ_FAIL", message: String(err?.message || err) } });
      }
      return;
    }

    if (scope === "config.write") {
      try {
        const updates = (msg.body && msg.body.updates) || {};
        const env = readEnvFile(ALLM_ENV_PATH);
        for (const k of ["LMSTUDIO_BASE_PATH","EMBEDDING_BASE_PATH","CHROMA_URL","VECTOR_DB"]) {
          if (Object.prototype.hasOwnProperty.call(updates, k) && updates[k] != null) env[k] = String(updates[k]);
        }
        writeEnvAtomically(ALLM_ENV_PATH, env);
        sendConfigReadResult(ws, msg.id, false);
      } catch (err) {
        wsSend(ws, { id: msg.id, type: "mcp.response", scope: "config.read.result", ok: false, error: { code: "WRITE_FAIL", message: String(err?.message || err) } });
      }
      return;
    }

    // Other scopes handled on the Orchestrator side; ignore here.
  };

  ws.onclose  = () => { log("warn", "MCP socket closed"); if (_hb) { clearInterval(_hb); _hb = null; } scheduleReconnect(); };
  ws.onerror  = (err) => { log("error", `WebSocket error ${err?.message || err}`); };
  return "connected";
}

// Auto-connect if local .env already present
try {
  const local = readEnvFile(LOCAL_ENV);
  if (local.AUTH && local.ORCH_URL) connect({ auth: local.AUTH, orch_url: local.ORCH_URL });
} catch (e) { log("warn", "auto-connect skipped", e?.message || e); }

// AnythingLLM agent skill contract
module.exports.runtime = {
  // The handler MUST return a string. Reference docs. 
  // Docs: plugin.json and handler.js rules. 
  // This satisfies Desktop loader that reads entrypoint.params and invokes runtime.handler. 
  handler: async function ({ action, orch_url, auth }) {
    const act = String(action || "status").toLowerCase();
    if (act === "configure") {
      const local = readEnvFile(LOCAL_ENV);
      if (auth) local.AUTH = auth;
      if (orch_url) local.ORCH_URL = orch_url;
      if (!local.AUTH) return "Please supply 'auth' Bearer token";
      if (!local.ORCH_URL) local.ORCH_URL = "ws://homeassistant.local:5005/mcp";
      writeEnvAtomically(LOCAL_ENV, local);
      return "configured";
    }
    if (act === "connect") { return `bridge ${connect({ orch_url, auth })}`; }
    if (act === "restart") { closeBridge(); return `bridge ${connect({ orch_url, auth })}`; }
    const hb = _hb ? "alive" : "idle";  // status
    const ws = _ws ? "open" : "closed";
    return `status ws=${ws} hb=${hb} url=${_orchUrl||"unset"}`;
  }
};
