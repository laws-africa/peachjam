<template>
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 id="documentProblemModalTitle" class="modal-title">
          {{ $t('Is there something wrong with this document?') }}
        </h5>
        <button
          type="button"
          class="btn-close"
          data-bs-dismiss="modal"
          aria-label="Close"/>
      </div>
      <div class="modal-body">
        <form
          v-if="!message.length"
          id="document-problem-form"
          ref="form"
          method="post"
          @submit.prevent="onSubmit"
        >
          <input
            type="hidden"
            name="document_link"
            :value="url"
          >
          <div class="form-group mb-2">
            <label for="problem_description">
              {{ $t("What's the problem?") }}
              <span class="text-danger">*</span>
            </label>
            <textarea
              id="problem_description"
              v-model="problem"
              class="form-control"
              name="problem_description"
              rows="4"
              required
            />
          </div>
          <div class="form-group">
            <label for="email_address">{{ $t('Your email address (optional)') }}</label>
            <input
              id="email_address"
              v-model="email"
              type="email"
              class="form-control"
              name="email_address"
              placeholder="example@example.com"
            >
          </div>
        </form>
        <div v-else>{{ message }}</div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
          {{ sent ? $t('Close') : $t('Cancel') }}
        </button>
        <button
          v-if="!message.length"
          type="submit"
          class="btn btn-success"
          form="document-problem-form"
        >
          {{ $t('Report problem') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DocumentProblemModal',
  data () {
    return {
      email: '',
      message: '',
      problem: '',
      sent: false,
      url: window.location.toString()
    };
  },
  mounted () {
    // attach a listener to the bootstrap modal events
    this.$el.parentElement.addEventListener('show.bs.modal', this.onShow);
  },
  methods: {
    onShow () {
      this.email = '';
      this.message = '';
      this.problem = '';
      this.sent = false;
    },
    onSubmit () {
      const form = new FormData(this.$refs.form);

      fetch('/document-problem/', {
        method: 'post',
        body: form
      }).then(response => {
        if (response.ok) {
          this.message = 'Thank you for your feedback.';
          this.sent = true;
        } else {
          this.message = 'Something went wrong.';
        }
      }).catch(error => {
        console.log(error);
      });
    }
  }
};

</script>
