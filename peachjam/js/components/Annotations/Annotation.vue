<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <div class="card">
      <div class="card-body">
        <div>
          <div class="dropdown text-end">
            <a
              id="dropdownMenuButton"
              class="btn btn-link"
              type="button"
              data-bs-toggle="dropdown"
              aria-haspopup="true"
              aria-expanded="false"
            >
              <i class="bi bi-three-dots" />
            </a>
            <div class="dropdown-menu" aria-labelledby="dropdownMenuButton">
              <a class="dropdown-item" @click="editAnnotation">Edit</a>
              <a class="dropdown-item" @click="deleteAnnotation">Delete</a>
            </div>
          </div>
        </div>
        <textarea
          v-if="editing"
          v-model="annotation.text"
          class="form-control grow-text"
        />
        <p v-else>
          {{ annotation.text }}
        </p>
        <div class="mt-2 text-end">
          <button
            v-if="editing"
            class="ms-1 btn btn-sm btn-secondary"
            @click="editing = false"
          >
            Cancel
          </button>

          <button
            v-if="editing"
            class="ms-1 btn btn-sm btn-primary"
            @click="saveAnnotation"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  </la-gutter-item>
</template>
<script>

import { authHeaders } from '../../api';

export default {
  name: 'AnnotationItem',
  props: {
    annotationData: {
      type: Object,
      default: null
    },
    viewRoot: HTMLElement,
    gutter: HTMLElement,
    useSelectors: Boolean
  },
  emits: ['edit-annotation', 'delete-annotation'],
  data: (x) => ({
    marks: [],
    anchorElement: null,
    editing: x.annotationData.editing || false,
    annotation: x.annotationData
  }),
  mounted () {
    this.anchorElement = document.getElementById(this.annotation.target_id);
    this.gutter.appendChild(this.$el);
  },
  methods: {
    editAnnotation () {
      this.editing = true;
    },
    async saveAnnotation () {
      const headers = await authHeaders();
      headers['Content-Type'] = 'application/json';

      const body = {
        text: this.annotation.text,
        target_selectors: this.annotation.target_selectors,
        target_id: this.annotation.target_id,
        document: this.annotation.document
      };

      const method = this.annotation.id === 'new' ? 'POST' : 'PUT';
      const url = this.annotation.id === 'new' ? '/api/annotations/' : `/api/annotations/${this.annotation.id}/`;
      const resp = await fetch(url, {
        method,
        headers,
        body: JSON.stringify(body)
      });

      if (resp.ok) {
        this.annotation = await resp.json();
        this.editing = false;
      }
    },
    async deleteAnnotation () {
      const headers = await authHeaders();
      const resp = await fetch(`/api/annotations/${this.annotation.id}/`, {
        method: 'DELETE',
        headers
      });
      if (resp.ok) {
        this.$el.remove();
      }
    }
  }
};
</script>

<style scoped>
.grow-text {
  field-sizing: content
}
</style>
