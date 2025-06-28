<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <div class="card">
      <div class="card-body">
        <div v-if="enrichment.enrichment_type==='unconstitutional_provision'" class="mb-1">
          <i class="bi bi-journal-x" />
          {{ $t('Unconstitutional provision') }}
        </div>
        <div v-else-if="enrichment.enrichment_type==='uncommenced_provision'" class="mb-1">
          <i class="bi bi-bell-slash" />
          {{ $t('Uncommenced provision') }}
        </div>
        <div v-if="enrichment.enrichment_type==='unconstitutional_provision'" class="mb-2">
          <span v-if="enrichment.resolved" class="badge bg-success">{{ $t( 'Resolved' ) }}</span>
          <span v-else class="badge bg-danger">{{ $t( 'Unresolved' ) }}</span>
        </div>
        <button
          v-if="enrichment.enrichment_type==='unconstitutional_provision'"
          type="button"
          class="btn btn-sm btn-secondary"
          data-bs-toggle="modal"
          :data-bs-target="'#provision-enrichment-modal-' + enrichment.id"
        >
          {{ $t( 'View details' ) }}
        </button>
        <div v-else-if="enrichment.enrichment_type==='uncommenced_provision' && !enrichment.and_all_descendants" class="small">
          <i class="bi bi-exclamation-triangle" />
          {{ $t('Some subprovisions are in force') }}
        </div>
      </div>
    </div>
  </la-gutter-item>
</template>
<script>

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
        this.marks.push(provision);
        if (this.enrichment.enrichment_type === 'unconstitutional_provision') {
          provision.classList.add('enrich-unconstitutional-provision');
        } else if (this.enrichment.enrichment_type === 'uncommenced_provision') {
          provision.classList.add('enrich-uncommenced-provision');
        }
        provision.clickFn = () => this.activate();
        provision.addEventListener('click', provision.clickFn);
        this.anchorElement = provision;
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
