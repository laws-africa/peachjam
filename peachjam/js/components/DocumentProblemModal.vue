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
            <label for="message">
              {{ $t('Problem category') }}
            </label>
            <select
              id="message"
              v-model="selectedOption"
              class="form-control"
              name="problem_category"
              :options="options"
              required
            >
              <option
                v-for="option in options"
                :key="option.text"
                :value="option.value"
              >
                {{ option.text }}
              </option>
            </select>
          </div>
          <div v-if="selectedOption === 'Other'">
            <label for="message">
              {{ $t('If other, please specify') }}
              <span class="text-danger">*</span>
            </label>
            <textarea
              id="other_problem_description"
              v-model="other"
              class="form-control"
              name="other_problem_description"
              required
            />
          </div>
          <div v-if="isVisible" class="form-group mb-2">
            <label for="problem_description">
              {{ $t("What's the problem?") }}
              <span class="text-danger">*</span>
            </label>
            <textarea
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
      submitted: false,
      success: true,
      url: window.location.toString(),
      selectedOption: '',
      other: '',
      isVisible: true,
      options: [
        { text: 'Incorrect information', value: 'Incorrect information' },
        { text: 'Missing information', value: 'Missing information' },
        { text: 'No PDF download', value: 'No PDF download' },
        { text: 'Document is empty', value: 'Document is empty' },
        { text: 'Document is not accessible on my device', value: 'Document is not accessible on my device' },
        { text: 'Other', value: 'Other' }
      ]
    };
  },
  mounted () {
    // attach a listener to the bootstrap modal events
    this.$el.parentElement.addEventListener('show.bs.modal', this.onShow);
  },
  methods: {
    onShow () {
      this.selectedOption = '';
      this.other = '';
      this.email = '';
      this.message = '';
      this.problem = '';
      this.submitted = false;
      this.success = true;
    },
    onSubmit () {
      const form = new FormData(this.$refs.form);

      fetch('/document-problem/', {
        method: 'post',
        body: form,
        headers: authHeaders()
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
