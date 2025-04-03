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
      <div class="card-body p-3">
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
  methods: {
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
