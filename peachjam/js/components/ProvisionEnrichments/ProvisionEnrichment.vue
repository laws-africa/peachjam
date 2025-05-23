<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <div class="card">
      <div class="card-body">
        <p>
          {{ $t('Unconstitutional provision') }}
          <span v-if="enrichment.resolved" class="badge bg-success">{{ $t( 'Resolved' ) }}</span>
          <span v-else class="badge bg-danger">{{ $t( 'Unresolved' ) }}</span>
        </p>

        <button
          type="button"
          class="btn btn-sm btn-secondary"
          data-bs-toggle="modal"
          :data-bs-target="'#provision-enrichment-modal-' + enrichment.id"
        >
          {{ $t( 'View details' ) }}
        </button>
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
    activate () {
      // Deactivate all
      Array.from(this.viewRoot.querySelectorAll('mark')).forEach(mark => {
        mark.classList.remove('active');
      });
      // Activate gutter item
      this.$el.active = true;
      // activate enrichment gutter item marks
      this.marks.forEach(mark => {
        mark.classList.add('active');
      });
    }
  }

};

</script>
