/* global URL, process */
import { gzipSync } from "node:zlib";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const assetDirectory = new URL("../dist/assets/", import.meta.url);
const limits = {
  charts: 220 * 1024,
  identity: 25 * 1024,
  index: 25 * 1024,
  settings: 8 * 1024,
  react: 70 * 1024,
  tanstack: 40 * 1024,
};

const JavaScriptAssets = readdirSync(assetDirectory).filter((name) =>
  name.endsWith(".js"),
);
const failures = [];

for (const name of JavaScriptAssets) {
  const group = Object.keys(limits).find((prefix) => name.startsWith(prefix));
  if (!group) continue;
  const bytes = gzipSync(
    readFileSync(join(assetDirectory.pathname, name)),
  ).length;
  const limit = limits[group];
  if (bytes > limit) failures.push(`${name}: ${bytes} bytes exceeds ${limit}`);
}

if (failures.length) {
  process.stderr.write(`Bundle budget exceeded\n${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("Production JavaScript bundle budgets passed\n");
