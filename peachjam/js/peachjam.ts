import components from './components';

// @ts-ignore
import { vueI18n } from './i18n';
import { createAndMountApp } from './utils/vue-utils';

import '@lawsafrica/law-widgets/dist/components/la-akoma-ntoso';
import '@lawsafrica/law-widgets/dist/components/la-gutter';
import '@lawsafrica/law-widgets/dist/components/la-gutter-item';
import '@lawsafrica/law-widgets/dist/components/la-table-of-contents-controller';
import '@lawsafrica/law-widgets/dist/components/la-decorate-external-refs';
import '@lawsafrica/law-widgets/dist/components/la-decorate-internal-refs';
import '@lawsafrica/law-widgets/dist/components/la-decorate-terms';
// @ts-ignore
import htmx from 'htmx.org';
import { csrfToken } from './api';

export interface PeachJamConfig {
  appName: string;
  pdfWorker: string;
  userHelpLink: string;
  sentry: {
    dsn: string | null;
    environment: string | null;
  }
}

class PeachJam {
  private components: any[];
  public config: PeachJamConfig = {
    appName: 'Peach Jam',
    pdfWorker: '/static/js/pdf.worker-prod.js',
    userHelpLink: '',
    sentry: {
      dsn: null,
      environment: null
    }
  };

  constructor () {
    this.components = [];
  }

  setup () {
    window.dispatchEvent(new Event('peachjam.before-setup'));
    this.setupConfig();
    // add the current user agent to the root HTML element for use with pocketlaw
    document.documentElement.setAttribute('data-user-agent', navigator.userAgent.toLowerCase());
    this.setupHtmx();
    this.setupSentry();
    this.createComponents(document.body);
    this.createVueComponents(document.body);
    this.setupTooltips();
    this.setupPopovers();
    this.setupSavedSearchModal();
    this.scrollNavTabs();
    this.clearGACookies();
    window.dispatchEvent(new Event('peachjam.after-setup'));
  }

  setupConfig () {
    const data = document.getElementById('peachjam-config')?.innerText;
    if (data) {
      this.config = JSON.parse(data);
    }
  }

  setupHtmx () {
    window.htmx = htmx;
    // htmx:load is fired both when the page loads (weird) and when new content is loaded. We only care about the latter
    // case. See https://github.com/bigskysoftware/htmx/issues/1500
    const htmxHelper = { firstLoad: true };
    let token: string = '';
    document.body.addEventListener('htmx:load', async (e) => {
      if (htmxHelper.firstLoad) {
        htmxHelper.firstLoad = false;
        return;
      }
      // mount components on new elements
      this.createComponents(e.target as HTMLElement);
      this.createVueComponents(e.target as HTMLElement);
    });

    htmx.on('htmx:confirm', (e:any) => {
      if (e.detail.verb === 'post') {
        e.preventDefault();
        csrfToken().then((t) => {
          token = t;
          e.detail.issueRequest();
        });
      }
    });

    htmx.on('htmx:configRequest', (e: any) => {
      if (e.detail.verb === 'post') {
        e.detail.headers['X-CSRFToken'] = token;
      }
    });
  }

  createComponents (root: HTMLElement) {
    if (root.getAttribute('data-component')) {
      this.createComponent(root);
    }
    // @ts-ignore
    for (const element of root.querySelectorAll('[data-component]')) {
      this.createComponent(element);
    }
    window.dispatchEvent(new Event('peachjam.components-created'));
  }

  createVueComponents (root: HTMLElement) {
    // create vue-based components
    // @ts-ignore
    for (const element of root.querySelectorAll('[data-vue-component]')) {
      this.createVueComponent(element);
    }
    window.dispatchEvent(new Event('peachjam.vue-components-created'));
  }

  createComponent (el: HTMLElement) {
    const name: string | null = el.getAttribute('data-component');
    if (name && components[name]) {
      // create the component and attached it to the HTML element
      (el as any).component = new components[name](el);
      this.components.push((el as any).component);
    }
  }

  createVueComponent (el: HTMLElement) {
    // create vue-based components
    const name = el.getAttribute('data-vue-component');
    if (name && components[name]) {
      const vueComp = components[name];
      createAndMountApp({
        component: vueComp,
        // pass in the element's data attributes as props
        props: { ...(el as HTMLElement).dataset },
        use: [vueI18n],
        mountTarget: el as HTMLElement
      });
      (el as any).component = vueComp;
      this.components.push(vueComp);
    }
  }

  setupSentry () {
    // @ts-ignore
    if (this.config.sentry && window.Sentry) {
      // @ts-ignore
      window.Sentry.init({
        dsn: this.config.sentry.dsn,
        environment: this.config.sentry.environment,
        allowUrls: [
          new RegExp(window.location.host.replace('.', '\\.') + '/static/')
        ],
        denyUrls: [
          new RegExp(window.location.host.replace('.', '\\.') + '/static/lib/pdfjs/')
        ],
        beforeSend (event: any) {
          try {
            // if there is no stacktrace, ignore it
            if (!event.exception || !event.exception.values || !event.exception.values[0] || !event.exception.values[0].stacktrace) {
              return null;
            }

            const frames = event.exception.values[0].stacktrace.frames;

            // if first frame is anonymous, don't send this event
            // see https://github.com/getsentry/sentry-javascript/issues/3147
            if (frames && frames.length > 0) {
              const firstFrame = frames[0];
              if (!firstFrame.filename || firstFrame.filename === '<anonymous>') {
                return null;
              }
            }
          } catch (e) {
            // ignore error, send event
            console.log(e);
          }

          return event;
        }
      });
    }
  }

  setupTooltips () {
    // setup bootstrap tooltips
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
      // @ts-ignore
      new window.bootstrap.Tooltip(el);
    });
  }

  setupPopovers () {
    document.querySelectorAll('[data-bs-toggle="help-popover"]').forEach((el) => {
      // @ts-ignore
      const helpPopover = new window.bootstrap.Popover(el, {
        html: true,
        content: `
        ${el.getAttribute('data-bs-content')}
         <div><a href="${el.getAttribute('href')?.split('#')[1] || '#'}" target='_blank' rel='noopener noreferrer'>Learn more</a></div>
        `,
        container: 'body'
      });
      // keep popover open when clicking inside it but close when clicking outside it
      el.addEventListener('inserted.bs.popover', (e) => {
        const popoverBody = document.querySelector('.popover-body');
        const clickListener = (e: MouseEvent) => {
          // Close the popover if the click is outside the popover
          if (!popoverBody?.contains(e.target as Node)) {
            helpPopover.hide();
            document.removeEventListener('click', clickListener);
          }
        };
        document.addEventListener('click', clickListener);
      });
    });
  }

  setupSavedSearchModal (): void {
    const savedSearchModal = document.getElementById('savedSearchModal') as HTMLElement | null;

    if (!savedSearchModal) {
      return;
    }

    savedSearchModal.addEventListener('show.bs.modal', (event: Event) => {
      const filters = savedSearchModal.querySelector('input[name="filters"]') as HTMLInputElement | null;
      const q = savedSearchModal.querySelector('input[name="q"]') as HTMLInputElement | null;

      if (!filters || !q) {
        console.error('Filters or query input not found');
        return;
      }

      const search = new URLSearchParams(window.location.search);
      q.value = search.get('q') || ''; // Default to an empty string if 'q' is null
      search.delete('q');
      filters.value = search.toString();
    });
  }

  scrollNavTabs () {
    // for scrollable tabbed navs, the active element may be out of view on narrow devices; scroll it into view
    document.querySelectorAll('.nav.nav-tabs.scroll-xs > .nav-item > .nav-link.active').forEach(link => {
      if (link.parentElement && link.parentElement.parentElement) {
        link.parentElement.parentElement.scrollLeft = (link as HTMLElement).offsetLeft;
      }
    });
  }

  clearGACookies () {
    // if window.dataLayer is not set, then Google Analytics is not enabled, but there may be cookies still set; clear them
    // @ts-ignore
    if (!window.dataLayer) {
      let cookies = [];
      try {
        cookies = document.cookie.split(';');
      } catch {
        // ignore security errors when reading cookies
        return;
      }
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i];
        const eqPos = cookie.indexOf('=');
        const name = eqPos > -1 ? cookie.substring(0, eqPos) : cookie;
        if (name.trim().startsWith('_ga')) {
          document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=.${window.location.hostname}`;
        }
      }
    }
  }
}

const peachJam = new PeachJam();
export default peachJam;
