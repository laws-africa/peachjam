<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <i
      :class="`bi ${icon} mobile-gutter-item-icon`"
      role="button"
      @click="activate"
    />
    <div class="card gutter-item-card">
      <div class="card-body">
        <div class="d-flex">
          <div v-if="enrichment.enrichment_type==='unconstitutional_provision'">
            <i :class="`bi ${icon}`" />
            {{ $t('Unconstitutional provision') }}
          </div>
          <div v-else-if="enrichment.enrichment_type==='uncommenced_provision'">
            <i :class="`bi ${icon}`" />
            {{ $t('Uncommenced provision') }}
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
      switch (this.enrichment.enrichment_type) {
        case 'unconstitutional_provision':
          return 'bi-journal-x';
        case 'uncommenced_provision':
          return 'bi-bell-slash';
      }
      return '';
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
          this.anchorElement.classList.add('enrich', 'enrich-unconstitutional-provision');
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
