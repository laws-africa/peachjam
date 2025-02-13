<template>
  <div id="provideFeedback" class="modal" tabindex="-1">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">
            Share your feedback
          </h5>
          <button
            type="button"
            class="btn-close"
            data-bs-dismiss="modal"
            aria-label="Close"
            @click="resetValues"
          />
        </div>
        <div class="modal-body">
          <div v-if="submitted">
            {{ success ? $t('Thank you for your feedback.') : $t('Something went wrong.') }}
          </div>
          <form v-else ref="feedbackForm">
            <input
              type="hidden"
              name="search_trace"
              :value="traceId"
            >
            <input
              type="hidden"
              name="user"
              :value="user?.id"
            >
            <div class="mb-3">
              <label for="name" class="col-form-label">Name</label>
              <input
                id="name"
                name="name"
                required
                :value="user?.username"
                type="text"
                class="form-control"
                maxlength="1024"
              >
            </div>
            <div class="mb-3">
              <label for="email" class="col-form-label">Email address</label>
              <input
                id="email"
                name="email"
                required
                :value="user?.email"
                type="email"
                class="form-control"
              >
            </div>
            <div class="mb-3">
              <label for="feedback" class="col-form-label">Message:</label>
              <textarea
                id="feedback"
                name="feedback"
                required
                class="form-control"
                maxlength="4096"
              />
            </div>
          </form>
        </div>
        <div class="modal-footer">
          <button
            type="button"
            class="btn btn-secondary"
            data-bs-dismiss="modal"
            @click="resetValues"
          >
            {{ submitted ? $t('Close') : $t('Cancel') }}
          </button>
          <button
            v-if="!submitted"
            type="button"
            class="btn btn-primary"
            @click="onSubmit"
          >
            Submit
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { authHeaders } from '../../api';

export default {
  name: 'ProvideFeedback',
  props: {
    traceId: {
      type: String,
      default: () => ''
    },
    user: {
      type: String,
      default: ''
    }
  },
  data () {
    return {
      submitted: false,
      success: false
    };
  },
  methods: {
    async onSubmit () {
      const form = new FormData(this.$refs.feedbackForm);

      fetch('/search/feedback/create', {
        method: 'post',
        body: form,
        headers: await authHeaders()
      }).then(response => {
        this.submitted = true;
        this.success = response.ok;
      }).catch(error => {
        console.log(error);
      });
    },
    resetValues () {
      this.submitted = false;
      this.success = false;
    }
  }
};
</script>
