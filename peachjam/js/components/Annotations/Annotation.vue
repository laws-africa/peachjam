<template>
  <la-gutter-item
    :id="annotation.id"
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
              <a class="dropdown-item" role="button" @click="editAnnotation">Edit</a>
              <a class="dropdown-item" role="button" @click="deleteAnnotation">Delete</a>
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
import { markRange, targetToRange } from '@lawsafrica/indigo-akn/dist/ranges';

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
  data: (x) => ({
    marks: [],
    anchorElement: null,
    editing: x.annotationData.editing || false,
    annotation: x.annotationData
  }),
  mounted () {
    this.anchorElement = document.getElementById(this.annotation.target_id);
    this.mark();
    this.gutter.appendChild(this.$el);
  },
  methods: {
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
      const url = this.annotation.id === 'new' ? `/api/documents/${this.annotation.document}/annotations/` : `/api/documents/${this.annotation.document}/annotations/${this.annotation.id}/`;
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
    editAnnotation () {
      this.editing = true;
    },
    async deleteAnnotation () {
      const headers = await authHeaders();
      const resp = await fetch(`/api/documents/${this.annotation.document}/annotations/${this.annotation.id}/`, {
        method: 'DELETE',
        headers
      });
      if (resp.ok) {
        this.unmark();
        this.$el.remove();
      }
    },
    mark () {
      const range = targetToRange({
        selectors: this.annotation.target_selectors,
        anchor_id: this.annotation.target_id
      }, this.viewRoot);
      if (!range) return;
      markRange(range, 'mark', mark => {
        this.marks.push(mark);
        return mark;
      }
      );
    },
    unmark () {
      this.marks.forEach(mark => {
        const parent = mark.parentNode;
        while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
        parent.removeChild(mark);
      });
      this.marks = [];
    }
  }
};
</script>

<style scoped>
.grow-text {
  field-sizing: content
}
</style>
