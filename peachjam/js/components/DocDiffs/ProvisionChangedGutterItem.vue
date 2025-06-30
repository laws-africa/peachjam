<template>
  <la-gutter-item
    :anchor="`#${provision.id}`"
  >
    <i
      class="bi bi-clock-history mobile-gutter-item-icon"
      role="button"
      @click="showChanges"
    />
    <div class="card d-none d-lg-block">
      <div class="card-body">
        <p>{{ $t('This provision has been amended') }}.</p>
        <button
          class="btn btn-sm btn-secondary"
          type="button"
          data-track-event="Document | What changed"
          @click="showChanges"
        >
          {{ $t('What changed?') }}
        </button>
      </div>
    </div>
  </la-gutter-item>
</template>

<script>
export default {
  name: 'ProvisionChangedGutterItem',
  props: {
    provision: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['show-changes'],
  data: () => ({
    anchorElement: null
  }),
  mounted () {
    this.setAnchor();
    // this can't be attached with vue's normal event listener because of the naming
    this.$el.addEventListener('laItemChanged', this.itemChanged);
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
      this.anchorElement = document.querySelector(`[data-eid="${this.provision.id}"`);
      if (this.anchorElement) {
        this.anchorElement.classList.add('enrich', 'enrich-changed-provision');
      }
    },
    activate () {
      this.$el.active = true;
      this.anchorElement.classList.add('active');
    },
    deactivate () {
      this.$el.active = false;
      this.anchorElement.classList.remove('active');
    },
    showChanges () {
      this.$el.dispatchEvent(new CustomEvent('show-changes', {
        detail: {
          provision: this.provision
        }
      }));
    }
  }
};
</script>
