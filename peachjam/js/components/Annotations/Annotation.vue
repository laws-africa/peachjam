<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <div class="card">
      <div class="card-body">
        <div class="d-flex mb-1">
          <div>
            <small class="fw-bold text-muted">{{ annotation.user }}</small>
          </div>
          <div class="dropdown ms-auto">
            <a
              class="dropdown-toggle"
              href="#"
              data-bs-toggle="dropdown"
              aria-haspopup="true"
              aria-expanded="false"
            />
            <ul class="dropdown-menu">
              <li>
                <a class="dropdown-item" role="button" @click="editAnnotation">{{ $t('Edit') }}</a>
              </li>
              <li>
                <a class="dropdown-item" role="button" @click="deleteAnnotation">{{ $t('Delete') }}</a>
              </li>
            </ul>
          </div>
        </div>
        <form @submit.prevent="saveAnnotation">
          <textarea
            v-if="editing"
            v-model="annotation.text"
            class="form-control grow-text"
            required
          />
          <div v-else>
            {{ annotation.text }}
          </div>
          <div v-if="editing" class="mt-2 text-end">
            <button
              class="btn btn-sm btn-secondary"
              @click="cancelEdit"
            >
              {{ $t('Cancel') }}
            </button>

            <button
              class="ms-1 btn btn-sm btn-primary"
              type="submit"
            >
              {{ $t('Save') }}
            </button>
          </div>
        </form>
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
    editable: Boolean
  },
  emits: ['remove-annotation'],
  data: (x) => ({
    marks: [],
    anchorElement: null,
    editing: x.annotationData.id < 0,
    annotation: x.annotationData
  }),
  computed: {
    isNew () {
      return this.annotation.id < 0;
    }
  },
  mounted () {
    this.mark();
    this.gutter.appendChild(this.$el);
  },
  unmounted () {
    this.unmark();
  },
  methods: {
    async saveAnnotation (e) {
      if (!this.editable) return;
      const isDocumentSaved = document.querySelector('[data-saved-document]') !== null;
      if (!isDocumentSaved) {
        await window.htmx.ajax('post', `/saved-documents/create?doc_id=${this.annotation.document}`, {
          target: '.save-document-button'
        });
      }

      const headers = await authHeaders();
      headers['Content-Type'] = 'application/json';

      const body = {
        text: this.annotation.text,
        target_selectors: this.annotation.target_selectors,
        target_id: this.annotation.target_id,
        document: this.annotation.document
      };

      const method = !this.isNew ? 'PUT' : 'POST';
      const url = !this.isNew ? `/api/documents/${this.annotation.document}/annotations/${this.annotation.id}/` : `/api/documents/${this.annotation.document}/annotations/`;
      const resp = await fetch(url, {
        method,
        headers,
        body: JSON.stringify(body)
      });

      if (resp.ok) {
        Object.assign(this.annotation, await resp.json());
        this.editing = false;
      }
    },
    editAnnotation () {
      this.editing = true;
    },
    async deleteAnnotation () {
      if (!this.editable) return;
      if (!this.isNew) {
        if (confirm(this.$t('Are you sure you want to delete this comment?'))) {
          const headers = await authHeaders();
          const resp = await fetch(`/api/documents/${this.annotation.document}/annotations/${this.annotation.id}/`, {
            method: 'DELETE',
            headers
          });
          if (!resp.ok) {
            throw new Error('Failed to delete annotation');
          }
        }
      }
      this.$emit('remove-annotation', this.annotation);
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
      });
      if (this.marks.length) {
        this.anchorElement = this.marks[0];
      }
    },
    cancelEdit () {
      this.editing = false;
      if (this.isNew) {
        this.$emit('remove-annotation', this.annotation);
      }
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
