<template>
  <div
    class="modal fade"
    tabindex="-1"
    data-bs-keyboard="false"
    data-bs-backdrop="static"
    role="dialog"
    aria-hidden="true"
  >
    <div class="modal-dialog" role="document">
      <div class="modal-content">
        <form @submit.prevent="save" ref="form">
          <div class="modal-header">
            <h5 class="modal-title">
              Add relationship
            </h5>
            <button
              type="button"
              class="btn-close"
              aria-label="Close"
              @click="close"
            />
          </div>

          <div class="modal-body">
            stuff
          </div>

          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-secondary"
              @click="close"
            >
              Cancel
            </button>

            <button
              type="submit"
              class="btn btn-success"
            >
              Add
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'RelationshipEnrichmentModal',
  props: {
    enrichment: {
      type: Object,
      default: null
    }
  },
  emits: ['close', 'save'],

  mounted () {
    document.body.appendChild(this.$el);
    this.modal = new bootstrap.Modal(this.$el);
    this.$el.addEventListener('hidePrevented.bs.modal', this.close);
    this.modal.show();
  },

  unmounted () {
    this.modal.hide();
  },

  methods: {
    save () {
      this.$emit('save', this.enrichment);
    },

    close () {
      this.$emit('close');
    }
  }
};
</script>
