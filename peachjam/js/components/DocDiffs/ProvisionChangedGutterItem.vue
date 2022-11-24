<template>
  <la-gutter-item
    :anchor="`#${provision.id}`"
    class="d-none d-lg-block"
  >
    <div class="card">
      <div class="card-body p-3">
        <p>{{ $t('This provision has been amended') }}.</p>
        <button
          class="btn btn-sm btn-secondary"
          type="button"
          @click="showChanges"
        >
          {{ $t('What changed') }}?
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
