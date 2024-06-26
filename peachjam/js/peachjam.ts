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
    this.setupConfig();
    // add the current user agent to the root HTML element for use with pocketlaw
    document.documentElement.setAttribute('data-user-agent', navigator.userAgent.toLowerCase());
    this.setupSentry();
    this.createComponents();
    this.setupTooltips();
    this.setupPopovers();
    this.scrollNavTabs();
    this.clearGACookies();
  }

  setupConfig () {
    const data = document.getElementById('peachjam-config')?.innerText;
    if (data) {
      this.config = JSON.parse(data);
    }
  }

  createComponents () {
    document.querySelectorAll('[data-component]').forEach((el) => {
      const name: string | null = el.getAttribute('data-component');
      if (name && components[name]) {
        // create the component and attached it to the HTML element
        (el as any).component = new components[name](el);
        this.components.push((el as any).component);
      }
    });

    // create vue-based components
    document.querySelectorAll('[data-vue-component]').forEach((el) => {
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
    });
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
            // if all frames are anonymous, don't send this event
            // see https://github.com/getsentry/sentry-javascript/issues/3147
            if (frames && frames.length > 0 && frames.every((f: any) => f.filename === '<anonymous>')) {
              return null;
            }
          } catch (e) {
            // ignore error, send event
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
