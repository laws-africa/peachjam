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

const siteProfiles = {
  africanlii: "africanlii",
  zambialii: "zambialii",
};

function getProfileNameForSite(siteName) {
  if (siteProfiles[siteName]) {
    return siteProfiles[siteName];
  }

  if (pageProfiles[siteName]) {
    return siteName;
  }

  return "liiweb";
}

function getPagesForSite(siteName) {
  const profileName = getProfileNameForSite(siteName);
  return {
    profileName,
    pages: pageProfiles[profileName],
  };
}

module.exports = {
  getPagesForSite,
  getProfileNameForSite,
  pageProfiles,
  siteProfiles,
};
