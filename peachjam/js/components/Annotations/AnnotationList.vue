<template>
  <div>
    <annotation-item
      v-for="annotation in items"
      :key="annotation.ref_id"
      ref="gutter-item"
      :annotation-data="annotation"
      :view-root="viewRoot"
      :gutter="gutter"
      :editable="editable"
      @remove-annotation="removeAnnotation"
    />

    <div ref="permissionModal" class="modal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              {{ $t('Permission required') }}
            </h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            />
          </div>
          <div class="modal-body">
            <p>{{ $t('To add an annotation, please login or contact your administrator.') }}</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('Close') }}
            </button>
            <a href="/accounts/login/" type="button" class="btn btn-primary">{{ $t('Log in') }}</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import AnnotationItem from './Annotation.vue';
import { Modal } from 'bootstrap';
export default {
  name: 'AnnotationsList',
  components: {
    AnnotationItem
  },
  props: {
    viewRoot: HTMLElement,
    gutter: HTMLElement,
    editable: Boolean
  },
  data: () => ({
    items: []
  }),
  mounted () {
    this.getAnnotations();
  },
  methods: {
    getAnnotations () {
      if (!this.editable) return;
      fetch(`/api/documents/${this.viewRoot.dataset.documentId}/annotations/`)
        .then((resp) => {
          if (!resp.ok) {
            throw new Error('Failed to fetch annotations');
          }
          return resp.json();
        })
        .then((annotations) => {
          this.items = annotations.results.map((annotation) => ({
            ...annotation,
            ref_id: `annotation-${annotation.id}`
          }));
        })
        .catch((err) => {
          console.error(err);
        });
    },
    addAnnotation (target) {
      if (!this.editable) {
        const permissionModal = new Modal(this.$refs.permissionModal);
        permissionModal.show();
        return;
      }
      const newAnnotation = {
        ref_id: `new-annotation-${this.items.length + 1}`,
        text: '',
        target_selectors: target.selectors,
        target_id: target.anchor_id,
        document: this.viewRoot.dataset.documentId,
        editing: true
      };
      this.items.push(newAnnotation);
    },
    async removeAnnotation (annotation) {
      this.items = this.items.filter((item) => item.ref_id !== annotation.ref_id);
    }
  }
};
</script>
