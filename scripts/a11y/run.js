const puppeteer = require("puppeteer");
const { AxePuppeteer } = require("@axe-core/puppeteer");

const pageSets = require("./pages");

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21aa"];
const BLOCKING_IMPACTS = new Set(["critical", "serious"]);
const SHOULD_COLOR =
  process.env.NO_COLOR === undefined &&
  (process.env.FORCE_COLOR !== undefined || process.stdout.isTTY);
const ANSI = {
  reset: "\u001b[0m",
  bold: "\u001b[1m",
  dim: "\u001b[2m",
  red: "\u001b[31m",
  yellow: "\u001b[33m",
  green: "\u001b[32m",
  cyan: "\u001b[36m",
  gray: "\u001b[90m",
};

function parseArgs(argv) {
  const args = {};

  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (!item.startsWith("--")) {
      continue;
    }

    const [key, inlineValue] = item.slice(2).split("=", 2);
    if (inlineValue !== undefined) {
      args[key] = inlineValue;
      continue;
    }

    const nextValue = argv[i + 1];
    if (!nextValue || nextValue.startsWith("--")) {
      args[key] = "true";
      continue;
    }

    args[key] = nextValue;
    i += 1;
  }

  return args;
}

function usage() {
  return [
    "Usage: node scripts/a11y/run.js --app <app> --base-url <url>",
    "",
    "Example:",
    "  npm run a11y:local -- --app liiweb --base-url http://127.0.0.1:8000",
  ].join("\n");
}

function ensureRequiredArg(args, name) {
  if (!args[name]) {
    throw new Error(`Missing required argument --${name}\n\n${usage()}`);
  }
}

function color(text, ...styles) {
  if (!SHOULD_COLOR || styles.length === 0) {
    return text;
  }

  return `${styles.join("")}${text}${ANSI.reset}`;
}

function sortViolations(violations) {
  const rank = { critical: 0, serious: 1, moderate: 2, minor: 3, null: 4 };
  return [...violations].sort((left, right) => {
    const leftRank = rank[left.impact] ?? 99;
    const rightRank = rank[right.impact] ?? 99;
    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }

    return left.id.localeCompare(right.id);
  });
}

function formatTargets(nodes) {
  const targets = [];

  nodes.forEach((node) => {
    (node.target || []).forEach((target) => {
      if (!targets.includes(target)) {
        targets.push(target);
      }
    });
  });

  return targets.slice(0, 3).join(", ");
}

function normaliseWhitespace(text) {
  return (text || "").replace(/\s+/g, " ").trim();
}

function formatImpact(impact) {
  if (impact === "critical") {
    return color("CRITICAL", ANSI.bold, ANSI.red);
  }

  if (impact === "serious") {
    return color("SERIOUS", ANSI.bold, ANSI.yellow);
  }

  if (impact === "moderate") {
    return color("MODERATE", ANSI.bold, ANSI.cyan);
  }

  if (impact === "minor") {
    return color("MINOR", ANSI.bold, ANSI.gray);
  }

  return color((impact || "unknown").toUpperCase(), ANSI.bold);
}

function printNodeDetails(nodes) {
  (nodes || []).slice(0, 3).forEach((node, index) => {
    const target = formatTargets([node]);
    const html = normaliseWhitespace(node.html);
    const failureSummary = (node.failureSummary || "")
      .split("\n")
      .map((line) => normaliseWhitespace(line))
      .filter(Boolean)
      .slice(0, 3);

    console.log(`    node ${index + 1}:`);
    if (target) {
      console.log(`      target: ${target}`);
    }
    if (html) {
      console.log(`      html: ${html}`);
    }
    if (failureSummary.length > 0) {
      failureSummary.forEach((line) => {
        console.log(`      detail: ${line}`);
      });
    }
  });
}

function printViolationDetails(pageId, pageUrl, violations) {
  violations.forEach((violation) => {
    console.log(
      `  ${formatImpact(violation.impact)} ${color(violation.id, ANSI.bold)} ${violation.help}`
    );

    if (pageId) {
      console.log(`    page: ${pageId}`);
    }
    if (pageUrl) {
      console.log(`    url: ${pageUrl}`);
    }
    if (violation.helpUrl) {
      console.log(`    help: ${violation.helpUrl}`);
    }
    printNodeDetails(violation.nodes);
  });
}

function printPageHeader(targetId, resolvedUrl, message, colorStyle) {
  console.log(`${color(targetId, ANSI.bold, colorStyle)} ${message}`);
  console.log(`  ${color(resolvedUrl, ANSI.dim)}`);
}

async function allowOnlyFirstPartyTraffic(page, baseUrl) {
  const baseOrigin = new URL(baseUrl).origin;

  await page.setRequestInterception(true);
  page.on("request", async (request) => {
    try {
      const requestUrl = new URL(request.url());
      if (
        requestUrl.origin === baseOrigin ||
        requestUrl.protocol === "data:" ||
        requestUrl.protocol === "about:"
      ) {
        await request.continue();
        return;
      }
    } catch (error) {
      // Fall through and continue the request if URL parsing fails.
    }

    await request.abort();
  });
}

async function settlePage(page, settleTimeMs) {
  await page.waitForSelector("body", { timeout: 15000 });
  await page.evaluate(async () => {
    if (document.fonts && document.fonts.ready) {
      await document.fonts.ready;
    }
  });
  await new Promise((resolve) => setTimeout(resolve, settleTimeMs));
}

function fallbackPathWithoutEnglishPrefix(targetPath) {
  if (!targetPath.startsWith("/en/")) {
    return null;
  }

  const fallbackPath = targetPath.slice(3);
  return fallbackPath || "/";
}

async function gotoWithFallback(page, baseUrl, targetPath) {
  const primaryUrl = new URL(targetPath, baseUrl).toString();
  let response = await page.goto(primaryUrl, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });

  let resolvedUrl = primaryUrl;
  const fallbackPath = fallbackPathWithoutEnglishPrefix(targetPath);
  const shouldRetryWithoutPrefix =
    fallbackPath && response && response.status() === 404;

  if (shouldRetryWithoutPrefix) {
    const fallbackUrl = new URL(fallbackPath, baseUrl).toString();
    response = await page.goto(fallbackUrl, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    resolvedUrl = fallbackUrl;
  }

  if (!response) {
    throw new Error(`No HTTP response received for ${resolvedUrl}`);
  }

  if (response.status() >= 400) {
    throw new Error(`Page returned HTTP ${response.status()} for ${resolvedUrl}`);
  }

  return { response, resolvedUrl };
}

async function scanPage(browser, baseUrl, target, settleTimeMs) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1600, deviceScaleFactor: 1 });
  await allowOnlyFirstPartyTraffic(page, baseUrl);

  try {
    const { response, resolvedUrl } = await gotoWithFallback(
      page,
      baseUrl,
      target.path
    );

    await settlePage(page, settleTimeMs);

    const results = await new AxePuppeteer(page).withTags(WCAG_TAGS).analyze();
    const blockingViolations = sortViolations(
      results.violations.filter((violation) =>
        BLOCKING_IMPACTS.has(violation.impact)
      )
    );

    const pageReport = {
      id: target.id,
      url: resolvedUrl,
      pageTitle: await page.title(),
      httpStatus: response ? response.status() : null,
      timestamp: new Date().toISOString(),
      blockingViolations,
      results,
    };

    const criticalViolations = blockingViolations.filter(
      (violation) => violation.impact === "critical"
    ).length;
    const seriousViolations = blockingViolations.filter(
      (violation) => violation.impact === "serious"
    ).length;

    if (blockingViolations.length > 0) {
      printPageHeader(
        target.id,
        resolvedUrl,
        `${blockingViolations.length} blocking violation(s) (${criticalViolations} critical, ${seriousViolations} serious, ${results.violations.length} total)`,
        ANSI.red
      );
      printViolationDetails(target.id, resolvedUrl, blockingViolations);
    } else {
      printPageHeader(
        target.id,
        resolvedUrl,
        `0 blocking violation(s) (${criticalViolations} critical, ${seriousViolations} serious, ${results.violations.length} total)`,
        ANSI.green
      );
    }

    return {
      id: target.id,
      url: resolvedUrl,
      pageTitle: pageReport.pageTitle,
      httpStatus: pageReport.httpStatus,
      totalViolations: results.violations.length,
      blockingViolations: blockingViolations.length,
      criticalViolations,
      seriousViolations,
    };
  } finally {
    await page.close();
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  ensureRequiredArg(args, "app");
  ensureRequiredArg(args, "base-url");

  const app = args.app;
  const baseUrl = args["base-url"];
  const settleTimeMs = Number(args["settle-time-ms"] || 1000);
  const pages = pageSets[app];

  if (!pages) {
    throw new Error(
      `Unsupported app '${app}'. Available apps: ${Object.keys(pageSets).join(", ")}`
    );
  }

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    const pageSummaries = [];
    for (const target of pages) {
      try {
        // Keep the scans sequential so the local Django server remains predictable and the report ordering is stable.
        /* eslint-disable no-await-in-loop */
        pageSummaries.push(await scanPage(browser, baseUrl, target, settleTimeMs));
        /* eslint-enable no-await-in-loop */
      } catch (error) {
        const url = new URL(target.path, baseUrl).toString();
        const failure = {
          id: target.id,
          url,
          pageTitle: null,
          httpStatus: null,
          totalViolations: 0,
          blockingViolations: 0,
          criticalViolations: 0,
          seriousViolations: 0,
          pageError: true,
          error: error.stack || error.message,
        };

        printPageHeader(target.id, url, "scan failed", ANSI.red);
        console.error(`  ${failure.error}`);
        pageSummaries.push(failure);
      }
    }

    const summary = {
      app,
      baseUrl,
      scannedPages: pageSummaries.length,
      pageErrors: pageSummaries.filter((page) => page.pageError).length,
      blockingViolations: pageSummaries.reduce(
        (total, page) => total + page.blockingViolations,
        0
      ),
      criticalViolations: pageSummaries.reduce(
        (total, page) => total + page.criticalViolations,
        0
      ),
      seriousViolations: pageSummaries.reduce(
        (total, page) => total + page.seriousViolations,
        0
      ),
      pages: pageSummaries,
    };

    console.log("");
    console.log(
      `${color("Summary", ANSI.bold)}: ${summary.blockingViolations} blocking violation(s), ${summary.pageErrors} page error(s), ${summary.scannedPages} page(s) scanned`
    );

    if (summary.blockingViolations > 0 || summary.pageErrors > 0) {
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
