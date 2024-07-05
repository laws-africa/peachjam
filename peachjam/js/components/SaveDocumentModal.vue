<template>
    <p>hello</p>
  <!-- <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 id="SaveDocumentModalTitle" class="modal-title">
          {{ $t('Where do you want to save your document?') }}
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
          id="save-document-form"
          ref="form"
          method="post"
        >
          <div v-if="collections.length">
            <div v-for="collection in collections" :key="collection" class="form-check">
              <input
                :id="collection"
                class="form-check-input"
                type="radio"
                :v-model="saveTo"
                :value="collection"
              >
              <label class="form-check-label" :for="collection">
                {{ collection }}
              </label>
            </div>
          </div>
          <div>
            <div class="form-check">
              <input
                id="noCollection"
                class="form-check-input"
                type="radio"
                :v-model="saveTo"
                value="noCollection"
              >
              <label class="form-check-label" for="noCollection">
                {% trans "Don't save to a collection" %}
              </label>
            </div>
            <div class="form-check">
              <input
                id="newCollection"
                class="form-check-input"
                type="radio"
                :v-model="saveTo"
                value="newCollection"
              >
              <label class="form-check-label" for="newCollection">
                Create new collection
              </label>
            </div>
          </div>
        </form>
      </div>
    </div>
  </div> -->
</template>

<script>
import { authHeaders } from '../api';

export default {
  name: 'SaveDocumentModal',
  props: {
    collections: {
      type: Array,
      default: () => []
    }
  },
  data () {
    return {
      saveTo: ''
    };
  },
  methods: {
    onShow () {
      this.saveTo = '';
    },
    async onSubmit () {
      const form = new FormData(this.$refs.form);

      fetch('/document-problem/', {
        method: 'post',
        body: form,
        headers: await authHeaders()
      })
        .then((response) => {
          this.submitted = true;
          this.success = response.ok;
        })
        .catch((error) => {
          console.log(error);
        });
    }
  }
};
</script>
