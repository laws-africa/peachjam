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
  red: "\u001b[31m",
  green: "\u001b[32m",
  yellow: "\u001b[33m",
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

    if (!value || value.startsWith("--")) {
      args[key] = true;
      continue;
    }

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

function pluralize(count, singular, plural = `${singular}s`) {
  return count === 1 ? singular : plural;
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

function countAffectedNodes(violations) {
  return violations.reduce(
    (total, violation) => total + (violation.nodes ? violation.nodes.length : 0),
    0,
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

function normalizeFailureDetail(detail) {
  return collapseWhitespace(detail).replace(/^Fix (?:any|all) of the following:\s*/i, "");
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function formatPreview(values, limit, separator = ", ") {
  const items = unique(values);
  const preview = items.slice(0, limit);
  const remaining = Math.max(items.length - preview.length, 0);

  if (!preview.length) {
    return "";
  }

  const suffix = remaining > 0 ? ` (+${remaining} more)` : "";
  return `${preview.join(separator)}${suffix}`;
}

function collectTargetPreview(nodes) {
  return unique(
    nodes.map((node) => {
      if (!node.target || !node.target.length) {
        return "";
      }

      return collapseWhitespace(node.target.join(" -> "));
    }),
  );
}

function collectFailureExamples(nodes) {
  return unique(
    nodes.flatMap((node) =>
      getFailureDetails(node)
        .map((detail) => normalizeFailureDetail(detail))
        .filter(Boolean),
    ),
  );
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

function renderViolation(violation, options = {}) {
  const label = severityLabel(violation.impact);
  const color = severityColor(violation.impact);
  const affectedNodes = violation.nodes ? violation.nodes.length : 0;
  const headline =
    `${paint(`[${label}]`, ANSI.bold, color)} ${paint(violation.id, color)}: ` +
    `${violation.help}`;
  const lines = [`  ${headline}`];

  lines.push(`    affected nodes: ${affectedNodes}`);

  if (violation.helpUrl) {
    lines.push(`    help: ${violation.helpUrl}`);
  }

  const targets = formatPreview(collectTargetPreview(violation.nodes || []), 3);
  if (targets) {
    lines.push(`    targets: ${targets}`);
  }

  const [example] = collectFailureExamples(violation.nodes || []);
  if (example) {
    lines.push(`    example: ${example}`);
  }

  if (options.verbose) {
    violation.nodes.forEach((node, index) => {
      lines.push(`    node ${index + 1}:`);

      if (node.target && node.target.length) {
        lines.push(`      target: ${node.target.join(", ")}`);
      }

      if (node.html) {
        lines.push(`      html: ${collapseWhitespace(node.html)}`);
      }

      getFailureDetails(node).forEach((detail) => {
        lines.push(`      detail: ${detail}`);
      });
    });
  }

  return lines;
}

function renderPageError(result, options = {}) {
  const errorMessage = collapseWhitespace(result.error && result.error.message ? result.error.message : result.error);
  const lines = [
    paint(`ERROR ${result.pageId} - scan failed`, ANSI.bold, ANSI.red),
    `  url: ${result.url}`,
    `  error: ${errorMessage}`,
  ];

  if (options.verbose && result.error && result.error.stack) {
    result.error.stack
      .split("\n")
      .slice(1)
      .map((line) => collapseWhitespace(line))
      .filter(Boolean)
      .forEach((line) => {
        lines.push(`  stack: ${line}`);
      });
  }

  return lines.join("\n");
}

function renderPageResult(result, options = {}) {
  const counts = countBlockingViolations(result.violations);
  const affectedNodes = countAffectedNodes(result.violations);

  if (counts.total === 0) {
    return paint(`PASS ${result.pageId}`, ANSI.bold, ANSI.green);
  }

  const lines = [
    paint(
      `FAIL ${result.pageId} - ` +
        `${counts.total} blocking ${pluralize(counts.total, "violation")}, ` +
        `${affectedNodes} affected ${pluralize(affectedNodes, "node")}`,
      ANSI.bold,
      statusColor(true, false),
    ),
    `  url: ${result.url}`,
  ];

  sortViolations(result.violations).forEach((violation) => {
    lines.push(...renderViolation(violation, options));
  });

  return lines.join("\n");
}

function printSummary(totalPages, pageResults, pageErrors) {
  const pagesWithViolations = pageResults.filter((result) => result.violations.length > 0);
  const allViolations = pagesWithViolations.flatMap((result) => result.violations);
  const counts = countBlockingViolations(allViolations);
  const affectedNodes = countAffectedNodes(allViolations);
  const hasErrors = counts.total > 0 || pageErrors.length > 0;
  const color = statusColor(counts.total > 0, pageErrors.length > 0);
  const lines = [
    paint(`Build ${hasErrors ? "FAILED" : "PASSED"}`, ANSI.bold, color),
    "",
    `Pages scanned: ${totalPages}`,
    `Pages with blocking violations: ${pagesWithViolations.length}`,
    "Blocking violations: " +
      `${counts.total} (${counts.critical} critical, ${counts.serious} serious)`,
    `Affected nodes: ${affectedNodes}`,
    `Page errors: ${pageErrors.length}`,
  ];

  console.log(lines.join("\n"));

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
  const verbose = Boolean(args.verbose);
  const { pages } = getPagesForSite(siteName);

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const pageResults = [];
  const pageErrors = [];
  const renderedResults = [];

  try {
    for (const pageDefinition of pages) {
      try {
        const result = await scanPage(browser, baseUrl, pageDefinition);
        pageResults.push(result);
        renderedResults.push(renderPageResult(result, { verbose }));
      } catch (error) {
        const pageError = {
          pageId: pageDefinition.id,
          url: buildPageUrl(baseUrl, pageDefinition.path),
          error,
        };

        pageErrors.push(pageError);
        renderedResults.push(renderPageError(pageError, { verbose }));
      }
    }
  } finally {
    await browser.close();
  }

  printSummary(pages.length, pageResults, pageErrors);

  if (renderedResults.length) {
    console.log("");
  }

  renderedResults.forEach((output, index) => {
    if (index > 0) {
      console.log("");
    }

    console.log(output);
  });
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
