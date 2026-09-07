import { createServer } from "node:http";
import { createReadStream, existsSync, mkdirSync, openSync, statSync } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const STATIC_ROOT = resolve(ROOT, "artifacts/market-frontend/dist/public");
const BACKEND_ROOT = resolve(ROOT, "market-backend");
const PORT = Number(process.env.PORT || 3000);
const BACKEND_PORT = Number(process.env.PYTHON_BACKEND_PORT || 8080);
const isProduction = process.env.NODE_ENV === "production";
const localPython = join(ROOT, ".venv", "bin", "python");
const pythonBin = process.env.PYTHON_BIN || (existsSync(localPython) ? localPython : "python3");
const configuredJwtSecret = process.env.JWT_SECRET_KEY || process.env.SESSION_SECRET || process.env.JWT_SECRET || process.env.SECRET_KEY;

mkdirSync(join(ROOT, ".runtime-logs"), { recursive: true });
const backendLog = openSync(join(ROOT, ".runtime-logs/backend.log"), "a");
const backendEnv = {
  ...process.env,
  PYTHONUNBUFFERED: "1",
  PORT: String(BACKEND_PORT),
  ...(configuredJwtSecret ? {
    JWT_SECRET_KEY: process.env.JWT_SECRET_KEY || configuredJwtSecret,
    SESSION_SECRET: process.env.SESSION_SECRET || configuredJwtSecret,
  } : {}),
  ...(isProduction ? {} : {
    ALLOW_MONGOMOCK: process.env.ALLOW_MONGOMOCK || "true",
  }),
};
const backend = spawn(
  pythonBin,
  ["-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT), "--workers", "1"],
  { cwd: BACKEND_ROOT, env: backendEnv, stdio: ["ignore", backendLog, backendLog] },
);
backend.on("exit", (code, signal) => {
  console.error(`[backend] exited code=${code ?? "null"} signal=${signal ?? "null"}`);
});

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".pdf": "application/pdf",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function sendStatic(req, res) {
  const requested = decodeURIComponent(new URL(req.url || "/", "http://manus.local").pathname);
  const relative = requested.replace(/^\/+/, "");
  const candidate = resolve(STATIC_ROOT, normalize(relative));
  const safeRoot = `${STATIC_ROOT}${relative ? "/" : ""}`;
  const safe = candidate === STATIC_ROOT || candidate.startsWith(safeRoot);
  const file = safe && existsSync(candidate) && statSync(candidate).isFile() ? candidate : join(STATIC_ROOT, "index.html");
  if (!existsSync(file)) {
    res.writeHead(503, { "content-type": "text/plain; charset=utf-8" });
    res.end("Frontend build is not available yet.");
    return;
  }
  const headers = { "content-type": mimeTypes[extname(file).toLowerCase()] || "application/octet-stream" };
  if (file.endsWith("index.html")) headers["cache-control"] = "no-cache";
  res.writeHead(200, headers);
  if (req.method === "HEAD") res.end();
  else createReadStream(file).pipe(res);
}

async function proxyApi(req, res) {
  const target = new URL(req.url || "/", `http://127.0.0.1:${BACKEND_PORT}`);
  const headers = { ...req.headers, host: `127.0.0.1:${BACKEND_PORT}` };
  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body: ["GET", "HEAD"].includes(req.method || "GET") ? undefined : req,
      duplex: "half",
    });
    res.writeHead(upstream.status, Object.fromEntries(upstream.headers.entries()));
    if (req.method === "HEAD") return res.end();
    if (upstream.body) {
      for await (const chunk of upstream.body) res.write(chunk);
    }
    res.end();
  } catch {
    if (!res.headersSent) res.writeHead(503, { "content-type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ detail: "Backend is starting or unavailable" }));
  }
}

const server = createServer((req, res) => {
  if ((req.url || "").startsWith("/api/")) return proxyApi(req, res);
  return sendStatic(req, res);
});
server.listen(PORT, "0.0.0.0", () => {
  console.log(`Uhsyb Manus bridge listening on port ${PORT}`);
});

function shutdown() {
  server.close();
  backend.kill("SIGTERM");
  setTimeout(() => process.exit(0), 500);
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
process.on("exit", () => {
  try { backend.kill("SIGTERM"); } catch {}
});
