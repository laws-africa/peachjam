const fs = require("fs");
const path = require("path");

const pageProfiles = {
  africanlii: [
    { id: "home", path: "/en/" },
    { id: "search", path: "/en/search/" },
    { id: "judgment-list", path: "/en/judgments/" },
    { id: "legislation-list", path: "/en/legislation/" },
    {
      id: "judgment-detail",
      path: "/en/akn/aa-au/judgment/ecowascj/2016/52/eng@2016-11-09",
    },
    {
      id: "legislation-detail",
      path: "/en/akn/za/act/1979/70/eng@2020-10-22",
    },
    {
      id: "document-detail-with-downloads",
      path: "/en/akn/aa-au/act/pact/2005/non-aggression-and-common-defence/eng@2005-01-31",
    },
  ],
  liiweb: [
    { id: "home", path: "/en/" },
    { id: "search", path: "/en/search/" },
    { id: "judgment-list", path: "/en/judgments/" },
    { id: "legislation-list", path: "/en/legislation/all" },
    {
      id: "judgment-detail",
      path: "/en/akn/aa-au/judgment/ecowascj/2016/52/eng@2016-11-09",
    },
    {
      id: "legislation-detail",
      path: "/en/akn/za/act/1979/70/eng@2020-10-22",
    },
    {
      id: "document-detail-with-downloads",
      path: "/en/akn/aa-au/act/pact/2005/non-aggression-and-common-defence/eng@2005-01-31",
    },
  ],
  zambialii: [
    { id: "home", path: "/" },
    { id: "search", path: "/search/" },
    { id: "judgment-list", path: "/judgments/" },
    { id: "legislation-list", path: "/legislation/all" },
    {
      id: "legislation-detail",
      path: "/akn/za/act/1979/70/eng@2020-10-22",
    },
  ],
};

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const SETTINGS_IMPORT_PATTERN = /^from\s+([a-zA-Z0-9_]+)\.settings\s+import\s+\*/m;

function getSettingsPath(siteName) {
  return path.join(REPO_ROOT, siteName, "settings.py");
}

function appExists(siteName) {
  return fs.existsSync(getSettingsPath(siteName));
}

function getParentSiteName(siteName) {
  if (!appExists(siteName)) {
    return null;
  }

  const settings = fs.readFileSync(getSettingsPath(siteName), "utf8");
  const match = settings.match(SETTINGS_IMPORT_PATTERN);
  return match ? match[1] : null;
}

function inheritsFromSite(siteName, parentSiteName, visitedSites = new Set()) {
  if (!appExists(siteName) || visitedSites.has(siteName)) {
    return false;
  }

  visitedSites.add(siteName);

  const directParentSiteName = getParentSiteName(siteName);
  if (!directParentSiteName) {
    return false;
  }

  if (directParentSiteName === parentSiteName) {
    return true;
  }

  return inheritsFromSite(directParentSiteName, parentSiteName, visitedSites);
}

function isLiiShell(siteName) {
  return siteName === "liiweb" || inheritsFromSite(siteName, "liiweb");
}

function getProfileNameForSite(siteName, visitedSites = new Set()) {
  if (pageProfiles[siteName]) {
    return siteName;
  }

  if (!appExists(siteName) || visitedSites.has(siteName)) {
    return null;
  }

  visitedSites.add(siteName);

  const parentSiteName = getParentSiteName(siteName);
  if (!parentSiteName || parentSiteName === siteName) {
    return null;
  }

  return getProfileNameForSite(parentSiteName, visitedSites);
}

function getPagesForSite(siteName) {
  if (!appExists(siteName)) {
    throw new Error(`App "${siteName}" does not exist in this repo`);
  }

  const profileName = getProfileNameForSite(siteName);

  if (!profileName) {
    throw new Error(
      `Unsupported app "${siteName}" for this WCAG scan`,
    );
  }

  return {
    profileName,
    pages: pageProfiles[profileName],
  };
}

function getSupportedSites() {
  return fs
    .readdirSync(REPO_ROOT, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith("."))
    .map((entry) => entry.name)
    .filter((siteName) => appExists(siteName) && getProfileNameForSite(siteName));
}

module.exports = {
  appExists,
  getParentSiteName,
  getPagesForSite,
  getProfileNameForSite,
  getSupportedSites,
  isLiiShell,
  pageProfiles,
};
