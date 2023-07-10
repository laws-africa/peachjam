import { IRangeSelector, IRangeTarget, markRange, targetToRange } from '@lawsafrica/indigo-akn/dist/ranges';
import { GutterEnrichmentManager, IGutterEnrichmentProvider } from '@lawsafrica/indigo-akn/dist/enrichments';
import { createAndMountApp } from '../../utils/vue-utils';
import { vueI18n } from '../../i18n';
import CitationLinkModal from './CitationLinkModal.vue';
import CitationLinkGutterItem from './CitationLinkGutterItem.vue';
import { ComponentPublicInstance } from 'vue';

export interface ICitationLink {
  // TODO: id
  text: string;
  url: string;
  // eslint-disable-next-line camelcase
  target_id: string;
  // eslint-disable-next-line camelcase
  target_selectors: IRangeSelector[];
}

/**
 * Inserts citation links into rendered PDF documents, and allows admins to manage them.
 */
export default class PDFCitationLinks implements IGutterEnrichmentProvider {
  protected root: HTMLElement;
  protected links: ICitationLink[];
  protected manager: GutterEnrichmentManager;
  protected modal: ComponentPublicInstance | null = null;
  protected readonly = true;
  protected anchors: Map<ICitationLink, HTMLElement[]> = new Map<ICitationLink, HTMLElement[]>();
  protected gutterItems: Map<ICitationLink, HTMLElement> = new Map<ICitationLink, HTMLElement>();

  constructor (root: HTMLElement, manager: GutterEnrichmentManager) {
    this.root = root;
    this.manager = manager;
    const el = document.getElementById('citation-links');
    this.links = JSON.parse((el ? el.textContent : '') || '[]');

    // TODO: if !readonly
    this.readonly = false;
    this.insertLinks();
    if (!this.readonly) {
      this.modal = this.createModal();
      this.manager.addProvider(this);
    }
  }

  insertLinks () {
    for (const link of this.links) {
      this.applyLink(link);
    }
  }

  applyLink (link: ICitationLink) {
    const target = {
      anchor_id: link.target_id,
      selectors: link.target_selectors
    };
    const range = targetToRange(target, this.root);
    if (!range) return;

    const elements: HTMLElement[] = [];
    markRange(range, 'a', a => {
      a.setAttribute('href', link.url);
      elements.push(a);
      return a;
    });
    this.anchors.set(link, elements);

    if (!this.readonly && elements.length > 0) {
      // add a gutter item
      // @ts-ignore
      this.manager.gutter?.appendChild(this.createGutterItem(link, elements[0]));
    }
  }

  createModal () : ComponentPublicInstance {
    return createAndMountApp({
      component: CitationLinkModal,
      props: {},
      use: [vueI18n],
      mountTarget: document.createElement('div')
    });
  }

  createGutterItem (link: ICitationLink, anchor: HTMLElement): HTMLElement {
    const item = createAndMountApp({
      component: CitationLinkGutterItem,
      props: {
        enrichment: link,
        anchorElement: anchor,
        provider: this
      },
      use: [vueI18n],
      mountTarget: document.createElement('div')
    }).$el;
    this.gutterItems.set(link, item);
    return item;
  }

  editLink (link: ICitationLink) {
    if (this.modal) {
      // @ts-ignore
      this.modal.showModal(link).then((result: ICitationLink | null) => {
        if (result) {
          // TODO: update on server
          this.unapplyLink(link);
          this.applyLink(link);
        } else {
          this.deleteLink(link);
        }
      });
    }
  }

  deleteLink (link: ICitationLink) {
    this.unapplyLink(link);
    this.links.splice(this.links.indexOf(link), 1);
    // TODO: delete from server
  }

  unapplyLink (link: ICitationLink) {
    // remove the anchors
    for (const el of this.anchors.get(link) || []) {
      const span = document.createElement('span');
      span.innerText = el.innerText;
      el.parentElement?.insertBefore(span, el);
      el.remove();
    }

    this.anchors.delete(link);
    this.gutterItems.get(link)?.remove();
  }

  getButton (target: IRangeTarget): HTMLButtonElement | null {
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline-secondary';
    btn.type = 'button';
    btn.innerText = 'Link citation...';
    return btn;
  }

  addEnrichment (target: IRangeTarget): void {
    if (this.modal && target.selectors) {
      // get the selected text
      const quoteSelector = target.selectors.find((x) => x.type === 'TextQuoteSelector');
      if (quoteSelector) {
        const enrichment: ICitationLink = {
          text: quoteSelector.exact || '',
          url: '',
          target_id: target.anchor_id,
          target_selectors: target.selectors || []
        };

        // @ts-ignore
        this.modal.showModal(enrichment).then((result: ICitationLink | null) => {
          if (result) {
            // TODO: save the new enrichment
            this.links.push(enrichment);
            this.applyLink(enrichment);
          }
        });
      }
    }
  }
}
