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
      @delete-annotation="deleteAnnotation(annotation)"
      @edit-annotation="editAnnotation(annotation)"
    />
  </div>
</template>
<script>
import AnnotationItem from './Annotation.vue';
import { createAndMountApp } from '../../utils/vue-utils';
import AddAnnotation from './AddAnnotation.vue';
import { vueI18n } from '../../i18n';
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
    items: [],
    addAnnotationComponent: null
  }),
  methods: {
    addNote (target) {
      if (this.addAnnotationComponent) {
        this.addAnnotationComponent.$el.remove();
      }

      this.addAnnotationComponent = createAndMountApp({
        component: AddAnnotation,
        props: {
          gutter: this.gutter,
          target,
          viewRoot: this.root
        },
        use: [vueI18n],
        mountTarget: document.createElement('div')
      });

      this.addAnnotationComponent.$refs.annotationButton.addEventListener('click', () => {
        console.log();
        this.items.push({
          id: this.items.length + 1,
          annotation: {
            text: this.addAnnotationComponent.$refs.annotationInput.value,
            target
          }
        });
        this.addAnnotationComponent.$el.remove();
      });
    },
    deleteAnnotation (annotation) {
      console.log('delete annotation', annotation);
      this.items = this.items.filter(item => item.id !== annotation.id);
    },
    editAnnotation (annotation) {
      console.log('edit annotation', annotation);
    }
  }

};
</script>
