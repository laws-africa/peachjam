<template>
  <div>
    <annotation-item
      v-for="annotation in items"
      :key="annotation.id"
      ref="gutter-item"
      :annotation="annotation"
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
    items: [
      {
        id: 1,
        text: 'This is a test annotation',
        range: {
          start: 0,
          end: 10
        }
      },
      {
        id: 2,
        text: 'This is another test annotation',
        range: {
          start: 20,
          end: 30
        }
      }
    ]
  })

};
</script>
