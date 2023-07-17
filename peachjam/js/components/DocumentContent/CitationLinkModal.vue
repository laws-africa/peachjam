<template>
  <div
    class="modal fade"
    tabindex="-1"
    data-bs-backdrop="static"
    role="dialog"
    aria-hidden="true"
  >
    <div
      class="modal-dialog modal-lg"
      role="document"
    >
      <div class="modal-content" v-if="enrichment">
        <form
          ref="form"
          @submit.prevent="close"
        >
          <div class="modal-header">
            <h5 class="modal-title">
              {{ $t('Link citation') }}
            </h5>
            <button
              type="button"
              class="btn-close"
              @click="removeOrClose"
            />
          </div>

          <div class="modal-body">
            <p><b>{{ enrichment.text }}</b></p>
            <label class="form-label">Citation link or FRBR URI</label>
            <input
              v-model="enrichment.url"
              type="text"
              class="form-control"
              placeholder="eg. /akn/..."
              required
            >
          </div>

          <div class="modal-footer">
            <button
              v-if="!enrichment.id"
              type="button"
              class="btn btn-secondary"
              @click="remove"
            >
              Cancel
            </button>

            <button
              v-if="!enrichment.id"
              type="submit"
              class="btn btn-success"
            >
              Add
            </button>

            <button
              v-if="enrichment.id"
              type="button"
              class="btn btn-danger"
              @click="confirmRemove"
            >
              Delete
            </button>

            <button
              v-if="enrichment.id"
              type="submit"
              class="btn btn-success"
            >
              Close
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>

export default {
  name: 'CitationLinkModal',
  data: () => ({
    resolve: null,
    enrichment: null
  }),

  mounted () {
    document.body.appendChild(this.$el);
    this.modal = new window.bootstrap.Modal(this.$el);
    this.$el.addEventListener('hidePrevented.bs.modal', this.removeOrClose);
  },

  methods: {
    showModal (enrichment) {
      this.enrichment = enrichment;
      return new Promise((resolve) => {
        this.resolve = resolve;
        this.modal.show();
      });
    },

    remove () {
      this.resolve(null);
      this.modal.hide();
      this.enrichment = null;
    },

    close () {
      this.resolve(this.enrichment);
      this.modal.hide();
      this.enrichment = null;
    },

    removeOrClose () {
      if (this.enrichment.id) {
        this.close();
      } else {
        this.remove();
      }
    },

    confirmRemove () {
      if (confirm(this.$t('Are you sure?'))) {
        this.remove();
      }
    }
  }
};
</script>
