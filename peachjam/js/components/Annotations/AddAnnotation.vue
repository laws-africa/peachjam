<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <div class="card">
      <div class="card-body">
        <input ref="annotationInput" v-model="newAnnotation" type="text">
        <button ref="annotationButton" class="btn btn-sm btn-secondary" type="button" @click="addAnnotation">
          Add
        </button>
      </div>
    </div>
  </la-gutter-item>
</template>
<script>
export default {
  name: 'AddAnnotation',
  props: {
    target: {
      type: Object,
      default: null
    },
    viewRoot: HTMLElement,
    gutter: HTMLElement
  },
  data: () => ({
    anchorElement: null,
    newAnnotation: ''
  }),
  mounted () {
    this.anchorElement = document.getElementById(this.target.anchor_id);
    this.gutter.appendChild(this.$el);
  },
  methods: {
    addAnnotation () {
      // emit an event with the value of the input
      this.$emit('add-annotation', this.newAnnotation);
    }
  }
};
</script>
<style scoped>
  input {
    width: 100%;
  }
</style>
