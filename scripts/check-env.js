#!/usr/bin/env node
/**
 * check-env.js — onboarding sanity check.
 *
 * Plain Node.js on purpose, not TypeScript: this is a standalone dev-tooling
 * script that never ships to the browser and never needs Next.js's build
 * pipeline, so pulling in `tsx`/`ts-node` just to run it would be pure
 * overhead. It parses .env / frontend/.env.local itself (no dotenv
 * dependency) since the format here is simple KEY=VALUE lines.
 *
 * Usage:
 *   node scripts/check-env.js
 *
 * Exits 0 if every required variable is present and non-empty, 1 otherwise
 * (so it's safe to wire into a pre-dev hook or CI step later).
 */

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return null;
  const values = {};
  const text = fs.readFileSync(filePath, "utf8");
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim();
    values[key] = value;
  }
  return values;
}

function checkGroup(label, filePath, requiredKeys, notes) {
  console.log(`\n${label} (${path.relative(ROOT, filePath)})`);
  const values = parseEnvFile(filePath);

  if (values === null) {
    console.log(`  ✗ File not found. Copy the .example version and fill it in.`);
    return false;
  }

  let ok = true;
  for (const key of requiredKeys) {
    const value = values[key];
    if (!value) {
      console.log(`  ✗ ${key} — missing or empty`);
      ok = false;
    } else {
      console.log(`  ✓ ${key}`);
    }
  }

  if (notes) {
    for (const note of notes) console.log(`  · ${note}`);
  }

  return ok;
}

console.log("OpsVista environment check");
console.log("===========================");

const backendOk = checkGroup(
  "Backend",
  path.join(ROOT, ".env"),
  [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "CORS_ALLOWED_ORIGINS",
  ],
  [
    "Need GEMINI_API_KEY or OPENAI_API_KEY set for real (non-mock) embeddings/generation.",
    "GOOGLE_DRIVE_CREDENTIALS_PATH and REINDEX_AUTOMATION_TOKEN are optional — only needed for real Drive ingestion / the scheduled reindex cron.",
  ],
);

const backendEnv = parseEnvFile(path.join(ROOT, ".env")) || {};
const hasLLMKey = Boolean(backendEnv.GEMINI_API_KEY || backendEnv.OPENAI_API_KEY);
console.log(
  hasLLMKey
    ? "  ✓ GEMINI_API_KEY or OPENAI_API_KEY set"
    : "  ✗ Neither GEMINI_API_KEY nor OPENAI_API_KEY set — chat will only work with USE_MOCK_EMBEDDINGS=true",
);

const frontendOk = checkGroup(
  "Frontend",
  path.join(ROOT, "frontend", ".env.local"),
  [
    "NEXT_PUBLIC_API_BASE_URL",
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  ],
  ["NEXT_PUBLIC_REQUIRE_AUTH defaults to false if unset — that's fine for local dev."],
);

console.log("\n===========================");
if (backendOk && frontendOk && hasLLMKey) {
  console.log("All required variables look set. You're good to run the app.");
  process.exit(0);
} else {
  console.log("Some required variables are missing — see ✗ marks above.");
  process.exit(1);
}
