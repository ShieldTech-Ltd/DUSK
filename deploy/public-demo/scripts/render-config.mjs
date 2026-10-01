import { readFile, mkdir, rename, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { deploymentConfig } from "../../../apps/console/scripts/deployment-config.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  if ([...value].some((character) => character.charCodeAt(0) < 32))
    throw new Error(`${name} contains a control character`);
  return value;
}

function endpoint(name) {
  const value = required(name);
  const url = new URL(value);
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/"
  )
    throw new Error(`${name} must be an HTTPS origin`);
  return url;
}

function replaceAll(template, values) {
  let output = template;
  for (const [name, value] of Object.entries(values)) {
    const marker = `@@${name}@@`;
    if (!output.includes(marker)) throw new Error(`Missing ${marker} marker`);
    output = output.replaceAll(marker, value);
  }
  if (/@@[A-Z_]+@@/.test(output)) throw new Error("Unresolved template marker");
  return output;
}

async function atomicWrite(path, content, mode = 0o640) {
  await mkdir(dirname(path), { recursive: true, mode: 0o750 });
  const temporary = `${path}.new`;
  await writeFile(temporary, content, { mode });
  await rename(temporary, path);
}

const output = resolve(process.argv[2] ?? "/opt/dusk/config");
const slot = required("DUSK_SLOT");
if (!new Set(["blue", "green"]).has(slot)) throw new Error("DUSK_SLOT must be blue or green");
const consoleUrl = endpoint("CONSOLE_URL");
const apiUrl = endpoint("API_URL");
const authUrl = endpoint("AUTH_URL");
const password = required("DEMO_VIEWER_PASSWORD");
if (password.length < 20 || password.length > 256)
  throw new Error("DEMO_VIEWER_PASSWORD must contain 20 to 256 characters");

const generated = deploymentConfig(
  {
    consoleUrl: consoleUrl.origin,
    apiBaseUrl: apiUrl.origin,
    oidcAuthority: `${authUrl.origin}/realms/dusk-demo`,
    oidcClientId: "dusk-console",
    environmentLabel: "Public Demo",
  },
  await readFile(resolve(root, "apps/console/nginx.conf"), "utf8"),
);
await atomicWrite(resolve(output, "console/config.json"), generated.config);
await atomicWrite(resolve(output, "console/nginx.conf"), generated.nginx);

const realmTemplate = replaceAll(
  await readFile(resolve(root, "deploy/public-demo/keycloak/dusk-demo-realm.template.json"), "utf8"),
  {
    CONSOLE_URL: consoleUrl.origin,
    DEMO_VIEWER_PASSWORD: "__DUSK_PASSWORD_PLACEHOLDER__",
  },
);
const realmObject = JSON.parse(realmTemplate);
const demoViewer = realmObject.users?.find((user) => user.username === "demo-viewer");
const passwordCredential = demoViewer?.credentials?.find(
  (credential) => credential.type === "password",
);
if (!passwordCredential) throw new Error("Missing demo-viewer password credential");
passwordCredential.value = password;
const realm = `${JSON.stringify(realmObject, null, 2)}\n`;
await atomicWrite(resolve(output, "keycloak/dusk-demo-realm.json"), realm);

const route = replaceAll(
  await readFile(resolve(root, "deploy/public-demo/traefik-route.template.yml"), "utf8"),
  {
    CONSOLE_HOST: consoleUrl.hostname,
    API_HOST: apiUrl.hostname,
    AUTH_HOST: authUrl.hostname,
    SLOT: slot,
  },
);
await atomicWrite(resolve(output, "traefik/routes.yml"), route, 0o644);
