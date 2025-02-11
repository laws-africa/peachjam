<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <p>{{ annotation.text }}</p>
  </la-gutter-item>
</template>
<script>
export default {
  name: 'AnnotationItem',
  props: {
    annotation: {
      type: Object,
      default: null
    },
    viewRoot: HTMLElement,
    gutter: HTMLElement,
    useSelectors: Boolean
  },
  data: () => ({
    marks: [],
    anchorElement: null
  }),

  mounted () {
    this.anchorElement = document.getElementById('arguments__para_6');
    this.gutter.appendChild(this.$el);
  }

};
</script>
