<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <i
      class="`bi bi-chat-left mobile-gutter-item-icon"
      role="button"
      @click="activate"
    />
    <div class="card gutter-item-card">
      <div class="card-body">
        <div class="d-flex mb-1">
          <div>
            <small class="fw-bold text-muted">{{ annotation.user }}</small>
          </div>
          <div class="dropstart ms-auto">
            <a
              class="bi bi-three-dots"
              href="#"
              data-bs-toggle="dropdown"
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
            v-model="text"
            class="form-control grow-text"
            required
          />
          <div v-else v-html="urlize(annotation.text)" />
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
    annotation: x.annotationData,
    text: x.annotationData.text
  }),
  computed: {
    isNew () {
      return this.annotation.id < 0;
    }
  },
  mounted () {
    this.mark();
    // this can't be attached with vue's normal event listener because of the naming
    this.$el.addEventListener('laItemChanged', this.itemChanged);
    this.gutter.appendChild(this.$el);
  },
  unmounted () {
    this.unmark();
  },
  methods: {
    async saveAnnotation (e) {
      if (!this.editable) return;
      this.annotation.text = this.text;

      const isDocumentSaved = document.querySelector('[data-saved-document]') !== null;
      if (!isDocumentSaved) {
        const el = document.createElement('div');
        await window.htmx.ajax('post', `/user/saved-documents/create?doc_id=${this.annotation.document}`, el);
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
    itemChanged () {
      // either the active or anchor state has changed
      if (this.$el.active) {
        this.activate();
      } else {
        this.deactivate();
      }
    },
    mark () {
      const range = targetToRange({
        selectors: this.annotation.target_selectors,
        anchor_id: this.annotation.target_id
      }, this.viewRoot);
      if (!range) return;
      markRange(range, 'mark', mark => {
        mark.classList.add('enrich', 'enrich-comment');
        mark.addEventListener('click', this.activate);
        this.marks.push(mark);
        return mark;
      });
      if (this.marks.length) {
        this.anchorElement = this.marks[0];
      }
    },
    cancelEdit () {
      this.editing = false;
      this.text = this.annotation.text;
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
    },
    activate () {
      this.$el.active = true;
      this.marks.forEach(mark => mark.classList.add('active'));
    },
    deactivate () {
      this.$el.active = false;
      this.marks.forEach(mark => mark.classList.remove('active'));
    },
    urlize (text) {
      const urlPattern = /(https?:\/\/[^\s]+)/g;

      const emailPattern = /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g;

      const domainPattern = /([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?=\s|$)/g;

      text = text.replace(urlPattern, (url) => {
        return `<a href="${url}" target="_blank">${url}</a>`;
      });

      text = text.replace(emailPattern, (email) => {
        return `<a href="mailto:${email}">${email}</a>`;
      });

      text = text.replace(domainPattern, (domain) => {
        return `<a href="http://${domain}" target="_blank">${domain}</a>`;
      });

      return text;
    }
  }
};
</script>

<style scoped>
.grow-text {
  field-sizing: content
}
</style>
