/**
 * Helper class to do common analytics tracking across both GA and Matomo.
 */
export class Analytics {
  isGAEnabled: boolean;
  isMatomoEnabled: boolean;
  isCustomerIOEnabled: boolean;

  constructor () {
    this.isGAEnabled = 'gtag' in window;
    this.isMatomoEnabled = '_paq' in window;
    this.isCustomerIOEnabled = 'cioanalytics' in window;
  }

  matomo (x: any) {
    if (this.isMatomoEnabled) {
      // @ts-ignore
      window._paq.push(x);
    }
  }

  gtag (...x: any[]) {
    if (this.isGAEnabled) {
      // @ts-ignore
      window.gtag(...x);
    }
  }

  customerio () {
    if (this.isCustomerIOEnabled) {
      // @ts-ignore
      return window.cioanalytics;
    }
    return {
      track: () => {},
      page: () => {},
      identify: () => {}
    };
  }

  trackPageView () {
    this.matomo(['trackPageView']);
    this.gtag('event', 'page_view');
    this.customerio().page();
  }

  trackSiteSearch (keyword: string, category: string, searchCount: number) {
    this.matomo(['trackSiteSearch', keyword, category, searchCount]);
    this.gtag('event', 'site_search', { keyword, category, searchCount });
  }

  trackEvent (category: string, action: string, name?: string, value?: number) {
    this.matomo(['trackEvent', category, action, name, value]);
    this.gtag('event', action, { event_category: category, event_name: name, value });
    this.customerio().track(`${category} ${action}`, {
      event_category: category,
      event_action: action,
      event_name: name,
    });
  }

  /**
   * Submit analytics events for clickable elements with data-track-event="Cat | Action | Name" attributes.
   */
  trackButtonEvents () {
    document.addEventListener('click', (e) => {
      if (e.target && e.target instanceof Element) {
        // find the closest element with the data-track-event attribute
        const trackable = e.target.closest('[data-track-event]');
        if (trackable) {
          const data = trackable.getAttribute('data-track-event');
          if (data && data.includes('|')) {
            const [category, action, name] = data.split('|').map(s => s.trim());
            this.trackEvent(category, action, name);
          }
        }
      }
    });
  }
}

const analytics = new Analytics();
export default analytics;
