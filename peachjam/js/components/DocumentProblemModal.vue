<template>
  <div class="modal-dialog">
    <div id="documentDetailModal" class="modal-content">
      <div class="modal-header">
        <h5 id="documentProblemModalTitle" class="modal-title">
          {{ $t('Is there something wrong with this document?') }}
        </h5>
        <button
          type="button"
          class="btn-close"
          data-bs-dismiss="modal"
          aria-label="Close"
        />
      </div>
      <div class="modal-body">
        <form
          v-if="!submitted"
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
            <label for="problem_category">
              {{ $t('Problem category') }}
              <span class="text-danger">*</span>
            </label>
            <select
              v-model="problem_category"
              class="form-control"
              name="problem_category"
              required
            >
              <option value="Incorrect information">
                {{ $t('Incorrect information') }}
              </option>
              <option value="Missing information">
                {{ $t('Missing information') }}
              </option>
              <option value="No PDF download">
                {{ $t('No PDF download') }}
              </option>
              <option value="Document is empty">
                {{ $t('Document is empty') }}
              </option>
              <option value="Document is not accessible on my device">
                {{ $t('Document is not accessible on my device') }}
              </option>
              <option value="Other">
                {{ $t('Other') }}
              </option>
            </select>
          </div>
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
            <label for="email_address">{{ $t('Your email address') }}
              <span class="text-danger">*</span>
            </label>
            <input
              id="email_address"
              v-model="email"
              type="email"
              class="form-control"
              name="email_address"
              placeholder="example@example.com"
              required
            >
          </div>
        </form>
        <div v-else>
          {{ success ? $t('Thank you for your feedback.') : $t('Something went wrong.') }}
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
          {{ submitted ? $t('Close') : $t('Cancel') }}
        </button>
        <button
          v-if="!submitted"
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
import { authHeaders } from '../api';

export default {
  name: 'DocumentProblemModal',
  data () {
    return {
      email: '',
      message: '',
      problem: '',
      problem_category: '',
      submitted: false,
      success: true,
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
      this.problem_category = '';
      this.submitted = false;
      this.success = true;
    },
    async onSubmit () {
      const form = new FormData(this.$refs.form);

      fetch('/document-problem/', {
        method: 'post',
        body: form,
        headers: await authHeaders()
      }).then(response => {
        this.submitted = true;
        this.success = response.ok;
      }).catch(error => {
        console.log(error);
      });
    }
  }
};

</script>
