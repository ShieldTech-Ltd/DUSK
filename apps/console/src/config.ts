export interface PublicConfig {
  apiBaseUrl: string;
  oidcAuthority: string;
  oidcClientId: string;
  environmentLabel: string;
}

let configPromise: Promise<PublicConfig> | undefined;

const fields = [
  "apiBaseUrl",
  "oidcAuthority",
  "oidcClientId",
  "environmentLabel",
] as const;

const maximumLength: Record<(typeof fields)[number], number> = {
  apiBaseUrl: 2048,
  oidcAuthority: 2048,
  oidcClientId: 256,
  environmentLabel: 128,
};

export function validateConfig(
  value: unknown,
  consoleUrl = location.href,
): PublicConfig {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Console configuration is invalid");
  const config = value as Record<string, unknown>;
  const loopback = (host: string) =>
    ["localhost", "127.0.0.1", "[::1]"].includes(host);
  const local = loopback(new URL(consoleUrl).hostname);
  if (Object.keys(config).some((field) => !fields.includes(field as never)))
    throw new Error("Console configuration is invalid");
  for (const field of fields) {
    if (
      typeof config[field] !== "string" ||
      !config[field].trim() ||
      config[field].length > maximumLength[field] ||
      [...config[field]].some(
        (character) =>
          character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127,
      )
    )
      throw new Error("Console configuration is invalid");
  }
  for (const field of ["apiBaseUrl", "oidcAuthority"] as const) {
    const url = new URL(config[field] as string);
    if (
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      (!local && loopback(url.hostname)) ||
      (url.protocol !== "https:" &&
        !(local && loopback(url.hostname) && url.protocol === "http:"))
    )
      throw new Error("Console endpoints require HTTPS outside localhost");
  }
  return config as unknown as PublicConfig;
}

export function loadConfig(): Promise<PublicConfig> {
  configPromise ??= fetch("/config.json", {
    cache: "no-store",
    credentials: "same-origin",
    redirect: "error",
  }).then(async (response) => {
    if (!response.ok) throw new Error("Console configuration is unavailable");
    return validateConfig(await response.json());
  });
  return configPromise;
}
