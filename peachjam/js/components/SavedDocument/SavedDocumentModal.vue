<template>
  <div
    class="modal fade"
    tabindex="-1"
    aria-hidden="true"
    ref="modal"
  >
    <div v-if="loading" class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-body">
          Loading...
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'SavedDocumentModel',
  props: ['url'],
  data: () => {
    return {
      loading: true,
      modal: null
    };
  },
  mounted () {
    document.body.appendChild(this.$el);
    this.modal = new window.bootstrap.Modal(this.$el);
  },
  methods: {
    show () {
      this.loading = true;
      this.modal.show();
      window.htmx.ajax('get', this.url, this.$refs.modal);
    }
  }
};
</script>
