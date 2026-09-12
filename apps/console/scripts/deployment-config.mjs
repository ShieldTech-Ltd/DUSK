import { readFile, mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const loopback = (host) => ["localhost", "127.0.0.1", "[::1]"].includes(host);

export function deploymentConfig(input, nginx) {
  const names = [
    "consoleUrl",
    "apiBaseUrl",
    "oidcAuthority",
    "oidcClientId",
    "environmentLabel",
  ];
  if (
    !input ||
    typeof input !== "object" ||
    Array.isArray(input) ||
    names.some(
      (key) =>
        typeof input[key] !== "string" ||
        !input[key].trim() ||
        input[key].length >
          {
            consoleUrl: 2048,
            apiBaseUrl: 2048,
            oidcAuthority: 2048,
            oidcClientId: 256,
            environmentLabel: 128,
          }[key] ||
        [...input[key]].some(
          (character) =>
            character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127,
        ),
    ) ||
    Object.keys(input).some((key) => !names.includes(key))
  ) {
    throw new Error(
      "Supply only consoleUrl, apiBaseUrl, oidcAuthority, oidcClientId and environmentLabel",
    );
  }
  const consoleUrl = new URL(input.consoleUrl);
  const local = loopback(consoleUrl.hostname);
  const urls = [
    consoleUrl,
    new URL(input.apiBaseUrl),
    new URL(input.oidcAuthority),
  ];
  for (const url of urls) {
    if (
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      (!local && loopback(url.hostname)) ||
      (url.protocol !== "https:" &&
        !(local && loopback(url.hostname) && url.protocol === "http:"))
    ) {
      throw new Error(
        "All deployment URLs require HTTPS outside localhost and must exclude credentials, queries and fragments",
      );
    }
    if (!/^https?:\/\/[a-z0-9.:[\]-]+$/i.test(url.origin))
      throw new Error("Invalid endpoint origin");
  }
  if (consoleUrl.pathname !== "/")
    throw new Error("Host the console at the origin root");
  const origins = [...new Set(urls.slice(1).map((url) => url.origin))].join(
    " ",
  );
  const csp = `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' ${origins}; font-src 'self'; object-src 'none'; base-uri 'none'; frame-src 'none'; frame-ancestors 'none'; form-action 'self' ${urls[2].origin}; manifest-src 'self'; media-src 'none'; worker-src 'none'; upgrade-insecure-requests`;
  const line = /^ {2}add_header Content-Security-Policy .*$/m;
  if (!line.test(nginx)) throw new Error("Missing CSP in nginx template");
  const publicConfig = Object.fromEntries(
    names.slice(1).map((name) => [name, input[name]]),
  );
  return {
    config: `${JSON.stringify(publicConfig, null, 2)}\n`,
    nginx: nginx.replace(
      line,
      `  add_header Content-Security-Policy "${csp}" always;\n  add_header Strict-Transport-Security "max-age=31536000" always;`,
    ),
  };
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const [inputPath, outputPath] = process.argv.slice(2);
  if (!inputPath || !outputPath)
    throw new Error(
      "Usage: npm run configure -- deployment.json output-directory",
    );
  const result = deploymentConfig(
    JSON.parse(await readFile(inputPath, "utf8")),
    await readFile(new URL("../nginx.conf", import.meta.url), "utf8"),
  );
  await mkdir(outputPath, { recursive: true });
  // Exclusive creation prevents overwriting previously reviewed deployment files.
  await writeFile(resolve(outputPath, "config.json"), result.config, {
    flag: "wx",
  });
  await writeFile(resolve(outputPath, "nginx.conf"), result.nginx, {
    flag: "wx",
  });
}
