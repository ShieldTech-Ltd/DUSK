const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const {
  hash,
  originalHash,
  patchedHash,
  patch,
  assess,
  apply,
  verifiedNodes,
} = require("./picomatch-backport.cjs");
const project = path.resolve(process.argv[2] || ".");
const installed = require.resolve("picomatch", { paths: [project] });
const pkg = path.dirname(installed);
const helper = fs.readFileSync(
  path.join(__dirname, "../../ci/picomatch-single-branch-helper.txt"),
  "utf8",
);
let original = fs.readFileSync(path.join(pkg, "lib/parse.js"), "utf8");
if (hash(original) === patchedHash) {
  original = original
    .replace(helper + "\n", "")
    .replace(
      "    const analysis = isFixedWidthRepeatedBranch(body)\n      ? analyzeRepeatedExtglob(body, opts)\n      : { risky: true };",
      "    const analysis = analyzeRepeatedExtglob(body, opts);",
    );
}
assert.equal(hash(original), originalHash);
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "dusk-glob-test-"));
fs.cpSync(pkg, path.join(directory, "original"), { recursive: true });
fs.cpSync(pkg, path.join(directory, "patched"), { recursive: true });
fs.writeFileSync(path.join(directory, "original/lib/parse.js"), original);
fs.writeFileSync(path.join(directory, "patched/lib/parse.js"), patch(original));
const before = require(path.join(directory, "original"));
const after = require(path.join(directory, "patched"));
process.on("exit", () =>
  fs.rmSync(directory, { recursive: true, force: true }),
);

test("only the known original parser can be repaired", () => {
  assert.equal(hash(patch(original)), patchedHash);
  assert.throws(() => patch(original + "\n"));
});

test("installed version, lock identity and modified parser cannot bypass admission", () => {
  const location = path.join(directory, "admission");
  const target = path.join(location, "node_modules/picomatch");
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.cpSync(pkg, target, { recursive: true });
  fs.writeFileSync(path.join(target, "lib/parse.js"), original);
  const lock = { packages: { "node_modules/picomatch": { version: "4.0.7" } } };
  fs.writeFileSync(
    path.join(location, "package-lock.json"),
    JSON.stringify(lock),
  );
  assert.throws(() => verifiedNodes(location));
  assert.equal(apply(location).length, 1);
  assert.deepEqual([...verifiedNodes(location)], ["node_modules/picomatch"]);
  fs.appendFileSync(path.join(target, "lib/parse.js"), "\n");
  assert.throws(() => verifiedNodes(location));
  assert.throws(() => apply(location));
  lock.packages["node_modules/picomatch"].version = "4.0.8";
  fs.writeFileSync(
    path.join(location, "package-lock.json"),
    JSON.stringify(lock),
  );
  assert.throws(() => apply(location));
});

test("known payload families remain bounded, including guard opt-out and unescape", () => {
  const patterns = [
    "+(*)b",
    "+(*a)b",
    "*(**a)b",
    "+(a**b)c",
    "+(*a@(a))b",
    "+(*a{a,b})c",
    "+(*a|b)c",
    "+(a\\+)b",
    "*(a\\*)b",
    "+([ab]*)c",
  ];
  for (const options of [
    {},
    { unescape: true },
    { maxExtglobRecursion: false },
    { capture: true },
    { bash: true },
  ]) {
    const code = `const pm=require(${JSON.stringify(path.join(directory, "patched"))}); for(const p of ${JSON.stringify(patterns)}) pm(p,${JSON.stringify(options)})('a'.repeat(256)+'X');`;
    const result = spawnSync(process.execPath, ["-e", code], {
      timeout: 2000,
      encoding: "utf8",
    });
    assert.equal(result.error, undefined, String(result.error));
    assert.equal(result.status, 0, result.stderr);
  }
});

test("ordinary tool globs and accepted literal repetitions preserve matches and captures", () => {
  const patterns = [
    "**/*.{js,ts,tsx}",
    "**/node_modules/**",
    "**/*.spec.ts",
    "@(src|test)/**",
    "!(node_modules)/**",
    "+(ab)",
    "*(a)",
    '+("*")',
    '*("*a")',
  ];
  const names = [
    "",
    "a",
    "aaa",
    "ab",
    "abab",
    "*",
    "**",
    "*a*a",
    "src/main.ts",
    "test/a.spec.ts",
    "node_modules/a.js",
    ".hidden/a.ts",
    "src/a.tsx",
  ];
  for (const options of [
    {},
    { dot: true },
    { unescape: true },
    { capture: true },
    { bash: true },
  ]) {
    for (const pattern of patterns)
      for (const name of names) {
        assert.equal(
          after(pattern, options)(name),
          before(pattern, options)(name),
          JSON.stringify({ pattern, name, options }),
        );
        if (options.capture)
          assert.deepEqual(
            after.makeRe(pattern, options).exec(name),
            before.makeRe(pattern, options).exec(name),
          );
      }
  }
});

test("intentionally disallowed repeated metacharacters are literalized, not flattened", () => {
  for (const pattern of ["+(*a)", "*(*a)", "+(a|b)", "+([ab])", "+(a\\*)"]) {
    assert.equal(after(pattern)(pattern), true);
    assert.equal(after(pattern)("aaaa"), false);
  }
});

test("audit disposition is limited to the exact repaired nodes and advisory", () => {
  const node = "node_modules/picomatch";
  const issue = {
    severity: "high",
    nodes: [node],
    via: [
      {
        name: "picomatch",
        url: "https://github.com/advisories/GHSA-fc5q-39xc-vjpf",
      },
    ],
  };
  const report = {
    metadata: {
      vulnerabilities: {
        info: 0,
        low: 0,
        moderate: 0,
        high: 2,
        critical: 0,
        total: 2,
      },
    },
    vulnerabilities: {
      picomatch: issue,
      vite: { severity: "high", via: ["picomatch"] },
    },
  };
  assert.deepEqual(assess(report, new Set([node]), "moderate").failures, []);
  assert.deepEqual(assess(report, new Set(), "moderate").failures, [
    "picomatch",
    "vite",
  ]);
  const changed = structuredClone(report);
  changed.vulnerabilities.picomatch.via.push({
    name: "picomatch",
    url: "https://github.com/advisories/another-issue",
  });
  assert.deepEqual(assess(changed, new Set([node]), "moderate").failures, [
    "picomatch",
    "vite",
  ]);
  assert.throws(() =>
    assess({ error: "offline" }, new Set([node]), "moderate"),
  );
  assert.throws(() =>
    assess(
      { ...report, metadata: { vulnerabilities: {} } },
      new Set([node]),
      "moderate",
    ),
  );
});
