import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const credentials = {
  viewer: "Viewer-local-208!",
  auditor: "Auditor-local-208!",
  investigator: "Investigate-local-208!",
} as const;

async function login(page: Page, username: keyof typeof credentials) {
  await page.goto("/login");
  await expect(
    page.getByText("Security Operations", { exact: true }),
  ).toHaveCount(1);
  await expect(
    page.getByRole("heading", {
      name: "Control agent actions before they become incidents.",
    }),
  ).toBeVisible();
  await expect(page.getByText("Authorization Code with PKCE")).toBeVisible();
  await page.getByRole("button", { name: "Continue securely" }).click();
  await expect(page).toHaveURL(/localhost:8081\/realms\/dusk-local/);
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(credentials[username]);
  await page.locator("#kc-login").click();
}

function observeUnexpectedFailures(page: Page) {
  const failures: string[] = [];
  page.on("console", (message) => {
    const source = message.location().url;
    if (
      message.type() === "error" &&
      (!source || source.startsWith("http://localhost:3000"))
    ) {
      failures.push(`console: ${message.text()}`);
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 500) {
      failures.push(
        `http ${response.status()}: ${new URL(response.url()).pathname}`,
      );
    }
  });
  return failures;
}

test("combined investigator can inspect every real-data surface", async ({
  page,
}) => {
  const failures = observeUnexpectedFailures(page);
  const initialSummary = page.waitForResponse(
    (response) =>
      response.url().includes("/v2/dashboard/summary") &&
      response.status() === 200,
  );
  await login(page, "investigator");
  const summaryData = await (await initialSummary).json();
  await expect(
    page.getByRole("heading", { name: "AI Agent Actions Under Control" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Security Operations" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(
    page.getByRole("button", { name: "Expand sidebar" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Decisions" })).toBeVisible();
  await page.getByRole("button", { name: "Expand sidebar" }).click();
  await expect(
    page
      .getByRole("region", { name: "Console status" })
      .getByText("Local Development"),
  ).toBeVisible();
  if (summaryData.decisions.value > 0) {
    await expect(
      page
        .locator(".kpi")
        .filter({ hasText: "Total decisions" })
        .locator("strong"),
    ).toHaveText(
      new Intl.NumberFormat("en-GB", {
        notation: "compact",
        maximumFractionDigits: 1,
      }).format(summaryData.decisions.value),
    );
  } else {
    await expect(
      page.getByText("No records in this window").first(),
    ).toBeVisible();
  }
  await expect(page.getByText(/^(Updated |Awaiting data)/)).toBeVisible();
  const decisionFeed = page.getByRole("table", {
    name: "Live persisted decisions",
  });
  await expect(
    decisionFeed
      .getByRole("row")
      .filter({ hasText: "netops-agent" })
      .filter({ hasText: "route change" }),
  ).toContainText("ALLOW");
  await expect(
    decisionFeed
      .getByRole("row")
      .filter({ hasText: "netops-agent" })
      .filter({ hasText: "firewall rule change" }),
  ).toContainText("BLOCK");

  const windowRequest = page.waitForResponse(
    (response) =>
      response.url().includes("/v2/dashboard/summary") &&
      response.url().includes("window=7d") &&
      response.status() === 200,
  );
  await page.getByLabel("UTC window").selectOption("7d");
  await windowRequest;
  await expect(page).toHaveURL(/window=7d/);

  const flowPanel = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Decision flow over time" }),
  });
  await flowPanel.getByRole("button", { name: "Show data table" }).click();
  await expect(
    page.getByRole("table", { name: "Decision flow data" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Decisions" }).click();
  await expect(
    page.getByRole("table", { name: "Persisted decisions" }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Decision verdict distribution" }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Decision volume over time" }),
  ).toBeVisible();
  const cursorRequest = page.waitForResponse(
    (response) =>
      response.url().includes("/v2/decisions") &&
      response.url().includes("cursor=") &&
      response.status() === 200,
  );
  const firstDecision = await page
    .getByRole("table", { name: "Persisted decisions" })
    .locator("tbody tr")
    .first()
    .locator("td")
    .allTextContents();
  await expect(
    page.getByRole("button", { name: "Previous page" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Next page" }).click();
  await cursorRequest;
  await page.getByRole("button", { name: "Previous page" }).click();
  await expect(
    page
      .getByRole("table", { name: "Persisted decisions" })
      .locator("tbody tr")
      .first()
      .locator("td"),
  ).toHaveText(firstDecision);
  await expect(
    page.getByRole("button", { name: "Previous page" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Next page" }).click();
  await page
    .getByRole("link", { name: /[0-9a-f]{8}-/ })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Decision investigation" }),
  ).toBeVisible();
  await expect(page.getByText("Safe canonical action")).toBeVisible();

  for (const route of [
    "Agents",
    "Policies",
    "Integrations",
    "Backend",
    "Audit",
  ]) {
    await page.getByRole("link", { name: route }).click();
    await expect(
      page.getByRole("heading", {
        name: new RegExp(route, "i"),
        level: 1,
      }),
    ).toBeVisible();
    if (route === "Agents") {
      await expect(
        page.getByRole("img", { name: "Agent risk ranking" }),
      ).toBeVisible();
      await page
        .getByRole("table", { name: "Agent risk rollups" })
        .getByRole("link")
        .first()
        .click();
      await expect(
        page.getByRole("img", {
          name: "Agent behavioral risk over recent decisions",
        }),
      ).toBeVisible();
      await expect(
        page.getByRole("img", { name: "Agent verdict profile" }),
      ).toBeVisible();
    } else if (route === "Policies") {
      await expect(
        page.getByRole("img", { name: "Policy rule lifecycle" }),
      ).toBeVisible();
      const showAll = page.getByRole("button", {
        name: /Show all \d+ policies/,
      });
      await expect(showAll).toBeVisible();
      await showAll.click();
      await expect(
        page.getByRole("button", { name: "Show first 24 policies" }),
      ).toBeVisible();
      await page.getByLabel("Find policy").fill("DUSK-NET-001");
      await expect(page).toHaveURL(/policy=DUSK-NET-001/);
      await expect(
        page
          .getByRole("table", { name: "Policy catalogue" })
          .getByRole("row")
          .filter({ hasText: "DUSK-NET-001" }),
      ).toContainText("Prevent unrestricted network exposure");
      await page.getByLabel("Find policy").fill("");
      await page
        .getByRole("combobox", { name: /^Severity/ })
        .selectOption("high");
      await expect(page).toHaveURL(/severity=high/);
    } else if (route === "Integrations") {
      await expect(
        page.getByRole("table", { name: "Measured integrations" }),
      ).toBeVisible();
      await expect(
        page.getByRole("img", { name: "Integration latency" }),
      ).toBeVisible();
      await expect(
        page.getByRole("cell", { name: "postgresql", exact: true }),
      ).toBeVisible();
      const refresh = page.waitForResponse(
        (response) =>
          response.url().includes("/v2/integrations/health") &&
          response.status() === 200,
      );
      await page.getByRole("button", { name: "Refresh snapshot" }).click();
      await refresh;
    } else if (route === "Backend") {
      await expect(
        page.getByRole("img", { name: "Backend component latency" }),
      ).toBeVisible();
      const backendCoverage = page.getByRole("table", {
        name: "Backend interface coverage",
      });
      await expect(backendCoverage).toBeVisible();
      await expect(backendCoverage).toContainText("/v1/gate");
      await expect(backendCoverage).toContainText("/v1/actions/evaluate");
      await expect(backendCoverage).toContainText("/v2/evaluations");
      await expect(backendCoverage).toContainText("/livez, /readyz");
    } else if (route === "Audit") {
      await expect(
        page.getByRole("img", { name: "Recent audit chain continuity" }),
      ).toBeVisible();
      await expect(
        page.getByRole("img", { name: "Audit sequence over time" }),
      ).toBeVisible();
    }
  }

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  expect(failures).toEqual([]);
});

test("viewer sees summaries but privileged investigation stays forbidden", async ({
  page,
}) => {
  const failures = observeUnexpectedFailures(page);
  await login(page, "viewer");
  await expect(
    page.getByRole("heading", { name: "Security Operations" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Agents" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Audit" })).toHaveCount(0);
  await page.evaluate(() => {
    window.history.pushState(null, "", "/audit");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await expect(page.getByText("Access forbidden")).toBeVisible();
  expect(failures).toEqual([]);
});

test("auditor lands on audit and can sign out", async ({ page }) => {
  const failures = observeUnexpectedFailures(page);
  await login(page, "auditor");
  await expect(
    page.getByRole("heading", { name: "Audit continuity" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Policies" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Overview" })).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/localhost:(3000|8081)/);
  expect(failures).toEqual([]);
});

test("mobile navigation and keyboard focus remain usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "investigator");
  await expect(
    page.getByRole("heading", { name: "Security Operations" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Decisions" })).toBeVisible();
  await page.getByRole("link", { name: "Decisions" }).click();
  await expect(
    page.getByRole("heading", { name: "Decisions", level: 1 }),
  ).toBeVisible();
  for (const panelName of [
    "Decision volume over time",
    "Enforcement distribution",
  ]) {
    const panelWidth = await page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: panelName }) })
      .evaluate((element) => element.getBoundingClientRect().width);
    expect(panelWidth).toBeGreaterThan(340);
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    ),
  ).toBeLessThanOrEqual(1);
  await expect(
    page.getByRole("region", { name: "Persisted decisions scroll area" }),
  ).toHaveAttribute("tabindex", "0");
  await page.keyboard.press("Tab");
  const focused = page.locator(":focus");
  await expect(focused).toBeVisible();
});
