<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <div class="card">
      <div class="card-body">
        <input v-model="newAnnotation" type="text">
        <button class="btn btn-sm btn-secondary" type="button" @click="addAnnotation" >
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
    console.log('mounting');
    console.log(this.target);
    this.anchorElement = document.getElementById(this.target.anchor_id);
    this.gutter.appendChild(this.$el);
  },
  methods: {
    addAnnotation () {
      // get the value of the input
      console.log(this.newAnnotation);
    }
  }
};
</script>
<style scoped>
  input {
    width: 100%;
  }
</style>
