<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <div class="card">
      <div class="card-body">
        <p>
          {{ $t('This provision was declared unconstitutional') }}
          <span v-if="enrichment.judgment">{{ $t('by') }} <a :href="enrichment.judgment.frbr_uri">{{ enrichment.judgment.title }}</a></span>
          <span v-if="enrichment.date_deemed_unconstitutional">{{ " " }}{{ $t('on') }} {{ enrichment.date_deemed_unconstitutional }}</span>
          <span>.</span>
          <span v-if="enrichment.resolved">{{ " " }}{{ $t('It has since been resolved.') }}</span>
        </p>

        <button class="btn btn-sm btn-secondary" :onclick="showModal">View details</button>
      </div>
    </div>
  </la-gutter-item>
</template>
<script>
import { markRange } from '@lawsafrica/indigo-akn/dist/ranges';
import { Modal } from 'bootstrap';
import { createApp, h } from 'vue';
import ProvisionEnrichmentModal from './ProvisionEnrichmentModal.vue';

export default {
  name: 'ProvisionEnrichment',
  props: {
    enrichment: {
      type: Object,
      default: null
    },
    viewRoot: HTMLElement,
    gutter: HTMLElement,
    useSelectors: Boolean,
    thisWorkFrbrUri: {
      type: String,
      default: ''
    }
  },
  data: () => ({
    marks: [],
    anchorElement: null
  }),
  mounted () {
    this.createModal();
    this.markAndAnchor();
    window.addEventListener('click', this.handleOutsideClick);
    this.gutter.appendChild(this.$el);
  },
  methods: {
    markAndAnchor () {
      const provision = document.querySelector(`[data-eid="${this.enrichment.provision_eid}"`);
      if (provision) {
        const range = document.createRange();
        range.selectNodeContents(provision);
        markRange(range, 'mark', mark => {
          this.marks.push(mark);
          mark.classList.add('unconstitutional-provision-highlight');
          mark.clickFn = () => this.activate();
          mark.addEventListener('click', mark.clickFn);
          return mark;
        });
        if (this.marks.length) {
          this.anchorElement = this.marks[0];
        }
      }
    },
    createModal () {
      const container = document.createElement('div');
      document.body.appendChild(container);
      const app = createApp({
        render: () => h(ProvisionEnrichmentModal, { enrichment: this.enrichment })
      });
      app.mount(container);
    },
    showModal () {
      const modal = new Modal(document.querySelector(`#provision-modal-${this.enrichment.id}`));
      modal.show();
    }
  }

};

</script>
