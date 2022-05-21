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
        <form @submit.stop="save" ref="form">
          <div class="modal-header">
            <h5 class="modal-title">
              {{ modalTitle }}
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
              v-if="!isNew"
              type="button"
              class="btn btn-danger mr-3"
              @click="deleteEnrichment"
            >
              Delete
            </button>

            <button
              type="button"
              class="btn btn-secondary"
              @click="close"
            >
              Close
            </button>

            <button
              v-if="isNew"
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
  props: ['enrichment'],
  emits: ['close', 'save', 'delete'],
  computed: {
    isNew () {
      return this.enrichment.id === null;
    },
    modalTitle () {
      return `${this.isNew ? 'Add' : 'Edit'} relationship enrichment`;
    }
  },

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
    close () {
      if (this.isNew) {
        // new, don't save it
        this.$emit('close');
      } else {
        this.save();
      }
    },

    save () {
      this.$emit('save', this.enrichment);
    },

    deleteEnrichment () {
      if (confirm('Are you sure?')) {
        this.$emit('delete', this.enrichment);
      }
    }
  }
};
</script>
