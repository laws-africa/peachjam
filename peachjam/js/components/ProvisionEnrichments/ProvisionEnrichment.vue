<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <i
      :class="`bi ${icon} mobile-gutter-item-icon ${mobileIconColour}`"
      role="button"
      @click="activate"
    />
    <!-- TODO: introduce and use a card-alert class -->
    <div :class="`card gutter-item-card alert ${alertLevel} p-0`">
      <div class="card-body">
        <div class="d-flex">
          <div>
            <i :class="`bi ${icon}`" /> <span
              v-if="enrichment.enrichment_type==='unconstitutional_provision'">{{ $t('Unconstitutional provision') }}
            </span>
            <span v-else-if="enrichment.enrichment_type==='uncommenced_provision'">{{ $t('Uncommenced provision') }}</span>
          </div>
          <button
            type="button"
            class="btn-close ms-auto d-lg-none"
            aria-label="Close"
            @click.stop="deactivate"
          />
        </div>
        <div v-if="enrichment.enrichment_type==='unconstitutional_provision'" class="mt-1">
          <span v-if="enrichment.resolved" class="badge bg-success">{{ $t( 'Resolved' ) }}</span>
          <span v-else class="badge bg-danger">{{ $t( 'Unresolved' ) }}</span>
        </div>
        <button
          v-if="enrichment.enrichment_type==='unconstitutional_provision'"
          type="button"
          class="btn btn-sm btn-secondary mt-2"
          data-bs-toggle="modal"
          :data-bs-target="'#provision-enrichment-modal-' + enrichment.id"
        >
          {{ $t( 'View details' ) }}
        </button>
        <div v-else-if="enrichment.enrichment_type==='uncommenced_provision' && !enrichment.and_all_descendants" class="mt-2 small">
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
    anchorElement: null
  }),
  computed: {
    icon () {
      if (this.enrichment.enrichment_type === 'unconstitutional_provision' && this.enrichment.resolved) {
        return 'bi-info-circle-fill';
      } else {
        return 'bi-exclamation-triangle-fill';
      }
    },
    mobileIconColour () {
      if (this.enrichment.enrichment_type === 'unconstitutional_provision' && !this.enrichment.resolved) {
        return 'text-danger';
      } else if (this.enrichment.enrichment_type === 'uncommenced_provision') {
        return 'text-warning';
      }
      // the default uses --bs-primary
      return null;
    },
    alertLevel () {
      if (this.enrichment.enrichment_type === 'unconstitutional_provision' && !this.enrichment.resolved) {
        return 'alert-danger';
      } else if (this.enrichment.enrichment_type === 'uncommenced_provision') {
        return 'alert-warning';
      }
      // for resolved unconstitutional provisions / the default
      return 'alert-primary';
    }
  },
  mounted () {
    this.setAnchor();
    // this can't be attached with vue's normal event listener because of the naming
    this.$el.addEventListener('laItemChanged', this.itemChanged);
    this.gutter.appendChild(this.$el);
  },
  methods: {
    itemChanged () {
      // either the active or anchor state has changed
      if (this.$el.active) {
        this.activate();
      } else {
        this.deactivate();
      }
    },
    setAnchor () {
      this.anchorElement = document.querySelector(`[data-eid="${this.enrichment.provision_eid}"`);
      if (this.anchorElement) {
        if (this.enrichment.enrichment_type === 'unconstitutional_provision') {
          if (!this.enrichment.resolved) {
            this.anchorElement.classList.add('enrich', 'enrich-unconstitutional-provision-unresolved');
          } else {
            this.anchorElement.classList.add('enrich', 'enrich-unconstitutional-provision-resolved');
          }
        } else if (this.enrichment.enrichment_type === 'uncommenced_provision') {
          this.anchorElement.classList.add('enrich', 'enrich-uncommenced-provision');
        }
        this.anchorElement.addEventListener('click', this.activate);
      }
    },
    activate () {
      this.$el.active = true;
      this.anchorElement.classList.add('active');
    },
    deactivate () {
      this.$el.active = false;
      this.anchorElement.classList.remove('active');
    }
  }
};

</script>
