<template>
  <la-gutter-item
    :anchor="`#${provision.id}`"
  >
    <i
      class="bi bi-clock-history"
      role="button"
      @click="showChanges"
    />
    <div class="card d-none d-lg-block">
      <div class="card-body p-3">
        <p>{{ $t('This provision has been amended') }}.</p>
        <button
          class="btn btn-sm btn-secondary"
          type="button"
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

<style scoped>
.bi-clock-history {
  font-size: 24px;
  color: var(--anntn-highlight-color);
  display: none;
  text-align: center;
  position: relative;
  z-index: 9;
}

@media screen and (max-width: 992px) {
  .bi-clock-history {
    display: block;
  }
}

</style>
