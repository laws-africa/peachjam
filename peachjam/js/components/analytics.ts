/**
 * Helper class to do common analytics tracking across both GA and Matomo.
 */
export class Analytics {
  isGAEnabled: boolean;
  isMatomoEnabled: boolean;
  gtag: any;
  paq: any[];

  constructor () {
    this.isGAEnabled = 'gtag' in window;
    this.isMatomoEnabled = '_paq' in window;

    // @ts-ignore
    this.gtag = this.isGAEnabled ? window.gtag : () => {};
    // @ts-ignore
    this.paq = this.isMatomoEnabled ? window._paq : [];
  }

  trackPageView () {
    this.paq.push(['trackPageView']);
    this.gtag('event', 'page_view');
  }

  trackSiteSearch (keyword: string, category: string, searchCount: number) {
    this.paq.push(['trackSiteSearch', keyword, category, searchCount]);
    this.gtag('event', 'site_search', { keyword, category, searchCount });
  }
}

const analytics = new Analytics();
export default analytics;
