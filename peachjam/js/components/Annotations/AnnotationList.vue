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
  data: (x) => ({
    items: x.annotations,
    addAnnotationComponent: null
  }),
  methods: {
    addAnnotation (target) {
      this.items = this.items.filter(item => item.id !== 'new');
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
