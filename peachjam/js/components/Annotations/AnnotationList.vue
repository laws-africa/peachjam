<template>
  <div>
    <annotation-item
      v-for="annotation in items"
      :key="annotation.id"
      ref="gutter-item"
      :annotation-data="annotation"
      :view-root="viewRoot"
      :gutter="gutter"
      :use-selectors="useSelectors"
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
    annotations: {
      type: Array,
      default: () => []
    },
    viewRoot: HTMLElement,
    gutter: HTMLElement,
    useSelectors: Boolean
  },
  data: () => ({
    items: []
  }),
  mounted () {
    this.getAnnotations();
  },
  methods: {
    getAnnotations () {
      fetch(`/api/annotations/?document=${this.viewRoot.dataset.documentId}`)
        .then((resp) => {
          if (!resp.ok) {
            throw new Error('Failed to fetch annotations');
          }
          return resp.json();
        })
        .then((annotations) => {
          this.items = annotations.results;})
        .catch((err) => {
          console.error(err);
        });
    },
    addAnnotation (target) {
      const unsaved = document.getElementById('new');
      if (unsaved) {
        unsaved.remove();
      }
      const newAnnotation = {
        id: 'new',
        text: '',
        target_selectors: target.selectors,
        target_id: target.anchor_id,
        document: this.viewRoot.dataset.documentId,
        editing: true
      };
      this.items.push(newAnnotation);
    }
  }
};
</script>
