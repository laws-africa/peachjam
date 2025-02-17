<template>
  <div>
    <annotation-item
      v-for="annotation in items"
      :key="annotation.id"
      ref="gutter-item"
      :annotation-data="annotation"
      :view-root="viewRoot"
      :gutter="gutter"
      @remove-annotation="removeAnnotation"
    />
  </div>
</template>
<script>
import AnnotationItem from './Annotation.vue';
export default {
  name: 'AnnotationsList',
  components: {
    AnnotationItem
  },
  props: {
    viewRoot: HTMLElement,
    gutter: HTMLElement
  },
  data: () => ({
    items: []
  }),
  mounted () {
    this.getAnnotations();
  },
  methods: {
    getAnnotations () {
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
