<template>
  <div class="mt-3 mb-5 d-lg-flex align-items-center">
    <p class="mb-lg-0 me-3">
      {{ $t("Can't find what you're looking for? Please let us know.") }}
    </p>
    <button class="btn btn-outline-primary" data-bs-toggle="modal" data-bs-target="#provideFeedback">
      {{ $t("Provide feedback") }}
    </button>
  </div>
  <div id="provideFeedback" class="modal" tabindex="-1">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">
            {{ $t("Share your feedback") }}
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
          <form
            v-else
            id="feedbackForm"
            ref="feedbackForm"
            method="post"
            @submit.prevent="onSubmit"
          >
            <input
              hidden
              name="search_trace"
              :value="traceId"
            >
            <div
              class="mb-3"
            >
              <label for="search-feedback_name" class="col-form-label">{{ $t("Name") }}</label>
              <input
                id="search-feedback_name"
                name="name"
                :value="userInfo?.name"
                type="text"
                class="form-control"
                maxlength="1024"
              >
            </div>
            <div class="mb-3">
              <label for="search-feedback_email" class="col-form-label">{{ $t("Email address") }}</label>
              <input
                id="search-feedback_email"
                name="email"
                :value="userInfo?.email"
                type="email"
                class="form-control"
              >
            </div>
            <div class="mb-3">
              <label for="search-feedback_feedback" class="col-form-label">{{ $t("What are you looking for?") }}</label>
              <textarea
                id="search-feedback_feedback"
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
            type="submit"
            class="btn btn-primary"
            form="feedbackForm"
          >
            {{ $t("Submit") }}
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
    }
  },
  data () {
    return {
      userInfo: {},
      submitted: false,
      success: false
    };
  },
  async mounted () {
    fetch('/accounts/user/', {
      method: 'get'
    }).then(async response => {
      if (response.ok) {
        this.userInfo = await response.json();
      }
    }).catch(error => {
      console.log(error);
    });
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
