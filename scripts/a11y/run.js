#!/usr/bin/env node

const puppeteer = require("puppeteer");
const { AxePuppeteer } = require("@axe-core/puppeteer");

const { getPagesForSite } = require("./pages");

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const BLOCKING_IMPACTS = new Set(["critical", "serious"]);
const IMPACT_ORDER = {
  critical: 0,
  serious: 1,
  moderate: 2,
  minor: 3,
  unknown: 4,
};

const ANSI = {
  reset: "\u001b[0m",
  bold: "\u001b[1m",
  dim: "\u001b[2m",
  red: "\u001b[31m",
  green: "\u001b[32m",
  yellow: "\u001b[33m",
  cyan: "\u001b[36m",
  gray: "\u001b[90m",
};

function supportsColor() {
  return Boolean(process.stdout && process.stdout.isTTY);
}

function paint(text, ...codes) {
  if (!supportsColor()) {
    return text;
  }

  return `${codes.join("")}${text}${ANSI.reset}`;
}

function parseArgs(argv) {
  const args = {};

  for (let i = 0; i < argv.length; i += 1) {
    const part = argv[i];

    if (!part.startsWith("--")) {
      continue;
    }

    const key = part.slice(2);
    const value = argv[i + 1];
    args[key] = value;
    i += 1;
  }

  return args;
}

function requireArg(args, name) {
  if (!args[name]) {
    throw new Error(`Missing required argument: --${name}`);
  }

  return args[name];
}

function normalizeBaseUrl(rawUrl) {
  const url = new URL(rawUrl);
  return url.toString().replace(/\/$/, "");
}

function collapseWhitespace(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function severityLabel(impact) {
  return String(impact || "unknown").toUpperCase();
}

function severityColor(impact) {
  if (impact === "critical") {
    return ANSI.red;
  }

  if (impact === "serious") {
    return ANSI.yellow;
  }

  return ANSI.gray;
}

function statusColor(hasBlocking, hasPageError) {
  if (hasPageError || hasBlocking) {
    return ANSI.red;
  }

  return ANSI.green;
}

function sortViolations(violations) {
  return [...violations].sort((left, right) => {
    const leftRank = IMPACT_ORDER[left.impact] ?? IMPACT_ORDER.unknown;
    const rightRank = IMPACT_ORDER[right.impact] ?? IMPACT_ORDER.unknown;

    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }

    return left.id.localeCompare(right.id);
  });
}

function countBlockingViolations(violations) {
  return violations.reduce(
    (counts, violation) => {
      const impact = violation.impact || "unknown";

      if (impact === "critical") {
        counts.critical += 1;
      }

      if (impact === "serious") {
        counts.serious += 1;
      }

      counts.total += 1;
      return counts;
    },
    { critical: 0, serious: 0, total: 0 },
  );
}

function getFailureDetails(node) {
  const details = [];

  if (node.failureSummary) {
    details.push(
      ...node.failureSummary
        .split("\n")
        .map((line) => collapseWhitespace(line))
        .filter(Boolean),
    );
  }

  return details;
}

function buildPageUrl(baseUrl, path) {
  return new URL(path, `${baseUrl}/`).toString();
}

function removeEnglishPrefix(urlString) {
  const url = new URL(urlString);

  if (url.pathname === "/en") {
    url.pathname = "/";
    return url.toString();
  }

  if (url.pathname.startsWith("/en/")) {
    url.pathname = url.pathname.slice(3) || "/";
    return url.toString();
  }

  return null;
}

async function gotoWithFallback(page, targetUrl) {
  const candidates = [targetUrl];
  const fallbackUrl = removeEnglishPrefix(targetUrl);

  if (fallbackUrl && fallbackUrl !== targetUrl) {
    candidates.push(fallbackUrl);
  }

  let lastError = null;

  for (const candidate of candidates) {
    const response = await page.goto(candidate, {
      waitUntil: "networkidle2",
      timeout: 60000,
    });

    const status = response ? response.status() : 200;

    if (status < 400) {
      return { response, url: candidate };
    }

    lastError = new Error(`Page returned HTTP ${status} for ${candidate}`);
  }

  throw lastError;
}

async function configurePage(page, allowedOrigin) {
  await page.setRequestInterception(true);

  page.on("request", (request) => {
    const requestUrl = request.url();

    if (
      requestUrl.startsWith("data:") ||
      requestUrl.startsWith("about:") ||
      requestUrl.startsWith("blob:")
    ) {
      request.continue();
      return;
    }

    try {
      const origin = new URL(requestUrl).origin;

      if (origin === allowedOrigin) {
        request.continue();
        return;
      }
    } catch (error) {
      request.continue();
      return;
    }

    request.abort();
  });
}

function printPageError(pageId, error) {
  console.log(
    paint(`${pageId} scan failed`, ANSI.bold, ANSI.red),
  );
  console.log(paint(error.stack || String(error), ANSI.red));
}

function printViolation(pageId, pageUrl, violation) {
  const label = severityLabel(violation.impact);
  const color = severityColor(violation.impact);

  console.log(
    `  ${paint(label, ANSI.bold, color)} ${paint(violation.id, color)} ${violation.help}`,
  );
  console.log(`    page: ${pageId}`);
  console.log(`    url: ${pageUrl}`);

  if (violation.helpUrl) {
    console.log(`    help: ${violation.helpUrl}`);
  }

  violation.nodes.forEach((node, index) => {
    console.log(`    node ${index + 1}:`);

    if (node.target && node.target.length) {
      console.log(`      target: ${node.target.join(", ")}`);
    }

    if (node.html) {
      console.log(`      html: ${collapseWhitespace(node.html)}`);
    }

    getFailureDetails(node).forEach((detail) => {
      console.log(`      detail: ${detail}`);
    });
  });
}

function printPageResult(result) {
  const counts = countBlockingViolations(result.violations);
  const header = `${result.pageId} ${counts.total} blocking violation(s) (${counts.critical} critical, ${counts.serious} serious, ${counts.total} total)`;

  console.log(
    paint(header, ANSI.bold, statusColor(counts.total > 0, false)),
  );
  console.log(`  ${result.url}`);

  sortViolations(result.violations).forEach((violation) => {
    printViolation(result.pageId, result.url, violation);
  });
}

function printSummary(totalBlockingViolations, pageErrors, scannedPages) {
  const hasErrors = totalBlockingViolations > 0 || pageErrors > 0;
  const color = statusColor(totalBlockingViolations > 0, pageErrors > 0);
  const summary = `Summary: ${totalBlockingViolations} blocking violation(s), ${pageErrors} page error(s), ${scannedPages} page(s) scanned`;

  console.log("");
  console.log(paint(summary, ANSI.bold, color));

  if (hasErrors) {
    process.exitCode = 1;
  }
}

async function scanPage(browser, baseUrl, pageDefinition) {
  const page = await browser.newPage();
  const targetUrl = buildPageUrl(baseUrl, pageDefinition.path);

  try {
    await configurePage(page, new URL(baseUrl).origin);
    const { url } = await gotoWithFallback(page, targetUrl);
    const analysis = await new AxePuppeteer(page).withTags(WCAG_TAGS).analyze();
    const blockingViolations = analysis.violations.filter((violation) =>
      BLOCKING_IMPACTS.has(violation.impact),
    );

    return {
      pageId: pageDefinition.id,
      url,
      violations: blockingViolations,
    };
  } finally {
    await page.close();
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const siteName = requireArg(args, "app");
  const baseUrl = normalizeBaseUrl(requireArg(args, "base-url"));
  const { pages } = getPagesForSite(siteName);

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  let totalBlockingViolations = 0;
  let pageErrors = 0;
  let scannedPages = 0;

  try {
    for (const pageDefinition of pages) {
      try {
        const result = await scanPage(browser, baseUrl, pageDefinition);
        totalBlockingViolations += result.violations.length;
        scannedPages += 1;
        printPageResult(result);
      } catch (error) {
        pageErrors += 1;
        printPageError(pageDefinition.id, error);
      }
    }
  } finally {
    await browser.close();
  }

  printSummary(totalBlockingViolations, pageErrors, scannedPages);
}

main().catch((error) => {
  console.error(paint(error.stack || String(error), ANSI.red));
  process.exit(1);
});
