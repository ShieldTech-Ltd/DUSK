import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";
import { test } from "node:test";
import { deploymentConfig } from "./deployment-config.mjs";

const nginx = await readFile(new URL("../nginx.conf", import.meta.url), "utf8");
const config = {
  consoleUrl: "https://console.example.com",
  apiBaseUrl: "https://api.example.com/v2-root",
  oidcAuthority: "https://identity.example.com/realms/company",
  oidcClientId: "dusk-console",
  environmentLabel: "Company sandbox",
};

test("generates a matching exact-origin CSP without localhost or wildcards", () => {
  const result = deploymentConfig(config, nginx);
  assert.equal(JSON.parse(result.config).apiBaseUrl, config.apiBaseUrl);
  assert.equal(JSON.parse(result.config).consoleUrl, undefined);
  assert.match(
    result.nginx,
    /connect-src 'self' https:\/\/api.example.com https:\/\/identity.example.com;/,
  );
  assert.match(
    result.nginx,
    /form-action 'self' https:\/\/identity.example.com/,
  );
  assert.doesNotMatch(result.nginx, /localhost|unsafe-inline|unsafe-eval|\*/);
  assert.match(result.nginx, /X-Content-Type-Options "nosniff" always/);
  assert.match(result.nginx, /frame-src 'none'/);
  assert.match(result.nginx, /worker-src 'none'/);
  assert.match(result.nginx, /upgrade-insecure-requests/);
  assert.match(result.nginx, /Cross-Origin-Resource-Policy "same-origin"/);
  assert.match(
    result.nginx,
    /Strict-Transport-Security "max-age=31536000" always/,
  );
});

test("rejects malformed or unsafe deployment settings before producing files", () => {
  for (const extra of [
    { apiBaseUrl: "http://api.example.com" },
    { apiBaseUrl: "https://localhost:8080" },
    { oidcAuthority: "https://user:password@identity.example.com" },
    { oidcAuthority: "https://identity.example.com?secret=value" },
    { consoleUrl: "https://console.example.com/subpath" },
    { oidcClientSecret: "must-not-be-public" },
    { oidcClientId: "" },
    { environmentLabel: "x".repeat(129) },
  ])
    assert.throws(() => deploymentConfig({ ...config, ...extra }, nginx));
});

test("supports explicit local development HTTP", () => {
  const result = deploymentConfig(
    {
      ...config,
      consoleUrl: "http://localhost:3000",
      apiBaseUrl: "http://localhost:8080",
      oidcAuthority: "http://localhost:8081/realms/dusk-local",
    },
    nginx,
  );
  assert.match(
    result.nginx,
    /connect-src 'self' http:\/\/localhost:8080 http:\/\/localhost:8081;/,
  );
});
