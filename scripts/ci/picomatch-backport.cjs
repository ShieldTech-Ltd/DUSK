// A transparent source backport. Package names and versions are never changed.
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { spawnSync } = require("node:child_process");
const originalHash =
  "4e1e05447668aa1e94366c5516a2bcd8f5fff800cc92b1d0cd7d77703b8618c4";
const patchedHash =
  "44709ecf02d78fd593fda0c995e788cab217d9846ec7a33e727df02bac9027de";
const advisory = "https://github.com/advisories/GHSA-fc5q-39xc-vjpf";
const expires = "2026-12-01";
const hash = (value) => crypto.createHash("sha256").update(value).digest("hex");
const helper = fs
  .readFileSync(
    path.join(__dirname, "../../ci/picomatch-single-branch-helper.txt"),
    "utf8",
  )
  .replace(/\r\n/g, "\n");
function patch(source) {
  if (hash(source) !== originalHash)
    throw new Error("Unknown picomatch parser; review required");
  function replaceOnce(text, before, after) {
    if (text.split(before).length !== 2)
      throw new Error("Backport context mismatch");
    return text.replace(before, after);
  }
  let result = replaceOnce(
    source,
    "const repeatedExtglobRecursion = pattern => {",
    helper + "\n\nconst repeatedExtglobRecursion = pattern => {",
  );
  result = replaceOnce(
    result,
    "    const analysis = analyzeRepeatedExtglob(body, opts);",
    "    const analysis = isFixedWidthRepeatedBranch(body)\n      ? analyzeRepeatedExtglob(body, opts)\n      : { risky: true };",
  );
  return result;
}
function inventory(project) {
  const lock = JSON.parse(
    fs.readFileSync(path.join(project, "package-lock.json"), "utf8"),
  );
  return Object.entries(lock.packages)
    .filter(([name]) => name.endsWith("node_modules/picomatch"))
    .map(([name, value]) => {
      if (
        name.split("/").includes("..") ||
        !name.startsWith("node_modules/") ||
        value.version !== "4.0.7"
      )
        throw new Error("Unknown picomatch lock entry");
      const directory = fs.realpathSync(path.join(project, name));
      const root = fs.realpathSync(path.join(project, "node_modules"));
      const relative = path.relative(root, directory);
      if (relative.startsWith("..") || path.isAbsolute(relative))
        throw new Error("Package escapes installation");
      const pkg = JSON.parse(
        fs.readFileSync(path.join(directory, "package.json"), "utf8"),
      );
      if (pkg.name !== "picomatch" || pkg.version !== "4.0.7")
        throw new Error("Unexpected installed package");
      return { node: name, file: path.join(directory, "lib/parse.js") };
    });
}
function checkExpiry() {
  if (new Date().toISOString().slice(0, 10) > expires)
    throw new Error("Backport disposition expired; review required");
}
function apply(project) {
  checkExpiry();
  const packages = inventory(project);
  for (const item of packages) {
    const source = fs.readFileSync(item.file, "utf8");
    if (hash(source) === patchedHash) continue;
    const result = patch(source);
    if (hash(result) !== patchedHash)
      throw new Error("Unexpected backport result");
    fs.writeFileSync(item.file, result);
  }
  return packages;
}
function verifiedNodes(project) {
  checkExpiry();
  const packages = inventory(project);
  for (const item of packages)
    if (hash(fs.readFileSync(item.file)) !== patchedHash)
      throw new Error("Backport absent or modified");
  return new Set(packages.map((item) => item.node));
}
function mitigated(name, report, nodes, visited = new Set()) {
  if (visited.has(name)) return false;
  const current = report.vulnerabilities[name];
  if (!current || !Array.isArray(current.via) || !current.via.length)
    return false;
  const next = new Set([...visited, name]);
  return current.via.every((via) =>
    typeof via === "string"
      ? mitigated(via, report, nodes, next)
      : name === "picomatch" &&
        via.name === "picomatch" &&
        via.url === advisory &&
        Array.isArray(current.nodes) &&
        current.nodes.length > 0 &&
        current.nodes.every((node) => nodes.has(node)),
  );
}
function assess(report, nodes, level) {
  const ranks = { info: 0, low: 1, moderate: 2, high: 3, critical: 4 };
  if (
    !Object.hasOwn(ranks, level) ||
    !report.metadata?.vulnerabilities ||
    !report.vulnerabilities ||
    report.error
  )
    throw new Error("Incomplete audit evidence");
  const entries = Object.entries(report.vulnerabilities);
  const summary = report.metadata.vulnerabilities;
  if (
    summary.total !== entries.length ||
    Object.keys(ranks).some(
      (severity) =>
        summary[severity] !==
        entries.filter(([, value]) => value.severity === severity).length,
    )
  )
    throw new Error("Audit summary does not match findings");
  const failures = [];
  const dispositions = [];
  for (const [name, value] of entries) {
    if (!Object.hasOwn(ranks, value.severity))
      throw new Error("Unknown audit severity");
    if (ranks[value.severity] < ranks[level]) continue;
    if (mitigated(name, report, nodes)) dispositions.push(name);
    else failures.push(name);
  }
  return { failures, dispositions };
}
function audit(project, level) {
  const nodes = verifiedNodes(project);
  const candidates = [
    process.env.npm_execpath,
    path.join(
      path.dirname(process.execPath),
      "node_modules/npm/bin/npm-cli.js",
    ),
    path.join(
      path.dirname(process.execPath),
      "../lib/node_modules/npm/bin/npm-cli.js",
    ),
  ];
  const cli = candidates.find(
    (candidate) =>
      candidate &&
      path.basename(candidate) === "npm-cli.js" &&
      fs.existsSync(candidate),
  );
  if (!cli) throw new Error("Trusted npm CLI not found");
  const result = spawnSync(process.execPath, [cli, "audit", "--json"], {
    cwd: project,
    encoding: "utf8",
    timeout: 120_000,
    maxBuffer: 16 * 1024 * 1024,
  });
  if (result.error || ![0, 1].includes(result.status))
    throw new Error("npm audit execution failed");
  const directory = path.join(project, "dependency-evidence");
  fs.mkdirSync(directory, { recursive: true });
  fs.writeFileSync(path.join(directory, "npm-audit.raw.json"), result.stdout);
  const report = JSON.parse(result.stdout);
  const decision = assess(report, nodes, level);
  fs.writeFileSync(
    path.join(directory, "picomatch-disposition.json"),
    JSON.stringify(
      {
        advisory,
        expires,
        originalHash,
        patchedHash,
        nodes: [...nodes],
        ...decision,
      },
      null,
      2,
    ),
  );
  console.log(JSON.stringify({ audit_level: level, ...decision }));
  if (decision.failures.length)
    throw new Error("Unmitigated dependency advisory blocks CI");
}
module.exports = {
  patch,
  hash,
  originalHash,
  patchedHash,
  apply,
  verifiedNodes,
  assess,
};
if (require.main === module) {
  const [command, project = ".", level = "moderate"] = process.argv.slice(2);
  try {
    if (command === "apply")
      console.log(
        `Verified backport applied to ${apply(path.resolve(project)).length} installed copies`,
      );
    else if (command === "audit") audit(path.resolve(project), level);
    else throw new Error("Use apply or audit");
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
