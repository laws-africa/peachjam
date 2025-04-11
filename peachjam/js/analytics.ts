/**
 * Helper class to do common analytics tracking across both GA and Matomo.
 */
export interface AnalyticsProvider {
  trackPageLoad: () => void;
  trackPageView: () => void;
  trackEvent: (category: string, action: string, name?: string, value?: number) => void;
  trackSiteSearch: (keyword: string, category: string, searchCount: number) => void;
}

export class Analytics {
  public providers: AnalyticsProvider[] = [];

  start () {
    this.setupButtonEvents();
    this.trackPageLoad();
  }

  trackPageLoad () {
    for (const provider of this.providers) {
      provider.trackPageLoad();
    }
  }

  trackPageView () {
    for (const provider of this.providers) {
      provider.trackPageView();
    }
  }

  trackSiteSearch (keyword: string, category: string, searchCount: number) {
    for (const provider of this.providers) {
      provider.trackSiteSearch(keyword, category, searchCount);
    }
  }

  trackEvent (category: string, action: string, name?: string, value?: number) {
    for (const provider of this.providers) {
      provider.trackEvent(category, action, name, value);
    }
  }

  /**
   * Submit analytics events for clickable elements with data-track-event="Cat | Action | Name" attributes.
   */
  setupButtonEvents () {
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

export class GA4 implements AnalyticsProvider {
  trackPageLoad () {
    // tracked automatically
  }

  trackPageView () {
    // @ts-ignore
    window.gtag('event', 'page_view');
  }

  trackEvent (category: string, action: string, name?: string, value?: number) {
    // @ts-ignore
    window.gtag('event', action, { event_category: category, event_name: name, value });
  }

  trackSiteSearch (keyword: string, category: string, searchCount: number) {
    // @ts-ignore
    window.gtag('event', 'site_search', { keyword, category, searchCount });
  }
}

export class Matomo implements AnalyticsProvider {
  trackPageLoad () {
    // tracked automatically
  }

  trackPageView () {
    // @ts-ignore
    window._paq.push(['trackPageView']);
  }

  trackEvent (category: string, action: string, name?: string, value?: number) {
    // @ts-ignore
    window._paq.push(['trackEvent', category, action, name, value]);
  }

  trackSiteSearch (keyword: string, category: string, searchCount: number) {
    // @ts-ignore
    window._paq.push(['trackSiteSearch', keyword, category, searchCount]);
  }
}

export class CustomerIO implements AnalyticsProvider {
  pageProperties: Record<string, any>;

  constructor () {
    // properties pushed with all page events
    this.pageProperties = JSON.parse(document.getElementById('track-page-properties')?.innerText || '{}');
  }

  trackPageLoad () {
    this.trackPageView();
  }

  trackPageView () {
    // @ts-ignore
    window.cioanalytics.page(this.pageProperties);
  }

  trackEvent (category: string, action: string, name?: string, value?: number) {
    const props = { ...this.pageProperties, event_category: category, event_action: action, event_name: name, value };
    // @ts-ignore
    window.cioanalytics.track(`${category} ${action}`, props);
  }

  trackSiteSearch (keyword: string, category: string, searchCount: number) {
    // TODO
  }
}

const analytics = new Analytics();

if ('gtag' in window) {
  analytics.providers.push(new GA4());
}

if ('_paq' in window) {
  analytics.providers.push(new Matomo());
}

if ('cioanalytics' in window) {
  analytics.providers.push(new CustomerIO());
}

export default analytics;
