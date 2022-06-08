<template>
  <div ref="snippet" />
</template>

<script>
export default {
  name: 'ResultSnippet',
  props: {
    node: {
      type: HTMLElement,
      required: true
    }
  },
  watch: {
    node (newNode) {
      this.$refs.snippet.innerHTML = '';
      this.$refs.snippet.appendChild(newNode);
    }
  },
  mounted () {
    this.$refs.snippet.appendChild(this.node);
  }
};
</script>

<style scoped>

</style>
