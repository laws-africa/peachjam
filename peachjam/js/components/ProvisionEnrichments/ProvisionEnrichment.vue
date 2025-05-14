<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <div class="card">
      <div class="card-body">
        <p>
          {{ enrichment.text }}
        </p>
      </div>
    </div>
  </la-gutter-item>
</template>
<script>
import { markRange } from '@lawsafrica/indigo-akn/dist/ranges';

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
    unmark () {
    },
    handleOutsideClick (event) {
      if (!this.$el.contains(event.target)) {
        this.unmark();
      }
    }
  }

};

</script>
