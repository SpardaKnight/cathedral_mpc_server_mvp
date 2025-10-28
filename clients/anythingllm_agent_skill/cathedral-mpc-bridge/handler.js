// Cathedral MPC Bridge - AnythingLLM Agent Skill (Desktop)
// Connects to HA MPC ws://.../mcp and provides deterministic .env read/write.
// Auto-starts on load. Exposes a runtime.handler so the Agent can call it.

"use strict";

const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const http = require("node:http");
const https = require("node:https");
const crypto = require("node:crypto");

const NativeWS = typeof WebSocket !== "undefined" ? WebSocket : null;
let WS = NativeWS;
if (!WS) { try { WS = require("ws"); } catch { WS = null; } }

function log(level, msg) {
  const ts = new Date().toISOString();
  console.log(`[Cathedral-MPC-Bridge][${level}] ${ts} ${msg}`);
}
function uid(prefix) { return `${prefix}-${crypto.randomBytes(8).toString("hex")}`; }

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
  const lines = Object.keys(map).map(k => {
    const v = String(map[k] ?? "");
    return `${k}=${needsQuotes(v) ? JSON.stringify(v) : v}`;
  });
  const tmp = `${ENV_PATH}.${Date.now()}.tmp`;
  fs.writeFileSync(tmp, lines.join("\n"), "utf8");
  fs.renameSync(tmp, ENV_PATH);
}
function normalize(obj) {
  const out = {};
  const keys = ["LMSTUDIO_BASE_PATH","EMBEDDING_BASE_PATH","CHROMA_URL","VECTOR_DB","STORAGE_DIR"];
  for (const k of keys) if (obj[k]) out[k] = obj[k].trim();
  out.orchestrator_upserts_only = true;
  return out;
}
function httpJson(url, timeoutMs = 3000) {
  return new Promise((resolve) => {
    const mod = url.startsWith("https") ? https : http;
    const req = mod.get(url, { timeout: timeoutMs }, (res) => {
      let buf = ""; res.setEncoding("utf8");
      res.on("data", (c) => buf += c);
      res.on("end", () => { try { resolve(JSON.parse(buf)); } catch { resolve(null); } });
    });
    req.on("error", () => resolve(null));
    req.on("timeout", () => { try { req.destroy(); } catch {} resolve(null); });
  });
}

const ORCH_URL = process.env.CATHEDRAL_MPC_URL || "ws://homeassistant.local:5005/mcp";
const AUTH = process.env.CATHEDRAL_MPC_TOKEN || "Bearer <SET_YOUR_HA_LONG_LIVED_TOKEN>";
const CLIENT = "anythingllm/desktop";
const VERSION = "v1.0";

function wsSend(ws, payload) { try { ws.send(JSON.stringify(payload)); } catch {} }

let ws = null;
let inFlight = null;
let backoff = 1000;

function connect() {
  if (!WS) { log("error", "No WebSocket available"); return; }
  try {
    ws = new WS(ORCH_URL, { headers: { Authorization: AUTH, "User-Agent": "Cathedral-MPC-Bridge" } });
  } catch (e) { log("error", `Failed to construct WebSocket: ${e?.message || e}`); return; }

  ws.onopen = async () => {
    log("info", `Connected to ${ORCH_URL}`); backoff = 1000;
    wsSend(ws, {
      id: uid("hello"), type: "mcp.request", scope: "handshake",
      headers: { authorization: AUTH, workspace_id: "ws_anythingllm", client: CLIENT, client_version: VERSION },
      body: { capabilities: ["config.read","config.write","session.*","memory.*"], orchestrator_upserts_only: true }
    });
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
      wsSend(ws, { id: uid("config.push"), type: "mcp.event", scope: "config.read.result", body });
    }, 2000);
  };

  ws.onmessage = (evt) => {
    let msg = {}; try { msg = JSON.parse(evt.data); } catch { return; }
    if (msg.type !== "mcp.request") return;
    const scope = msg.scope || "";
    if (scope === "config.read") {
      const body = normalize(readEnv());
      wsSend(ws, { id: msg.id || uid("config.read"), type: "mcp.response", ok: true, body });
    } else if (scope === "config.write") {
      try {
        const updates = msg.body?.updates || {};
        const current = readEnv();
        for (const [k, v] of Object.entries(updates)) current[k] = String(v ?? "");
        writeEnvAtomically(current);
        const body = normalize(current);
        wsSend(ws, { id: msg.id || uid("config.write"), type: "mcp.response", ok: true, body });
      } catch (e) {
        wsSend(ws, { id: msg.id || uid("config.write"), type: "mcp.response", ok: false, error: { code: "WRITE_FAIL", message: e?.message || String(e) } });
      }
    }
  };

  ws.onclose = () => { log("warn", "Socket closed"); ws = null; setTimeout(connect, backoff); backoff = Math.min(backoff * 2, 30000); };
  ws.onerror = (err) => { log("error", `Socket error: ${err?.message || err}`); };
}

function startBridge() { if (inFlight) return; inFlight = true; connect(); }
try { startBridge(); } catch (e) { log("error", `Bridge init failed: ${e?.message || e}`); }

module.exports.runtime = {
  handler: async function ({ command }) {
    const action = String(command || "status").toLowerCase();
    const caller = `${this.config.name}-v${this.config.version}`;
    try {
      this.introspect(`${caller} invoked with command=${action}`);
      if (action === "restart") {
        if (ws && ws.terminate) { try { ws.terminate(); } catch {} }
        ws = null; inFlight = null; startBridge();
        return "[Cathedral-MPC-Bridge] restart signal sent";
      }
      const env = normalize(readEnv());
      return `[Cathedral-MPC-Bridge] running. ws=${ORCH_URL}. env.keys=${Object.keys(env).join(",")}`;
    } catch (e) {
      this.introspect(`${caller} failed: ${e?.message || e}`);
      return `Bridge failed: ${e?.message || e}`;
    }
  }
};
