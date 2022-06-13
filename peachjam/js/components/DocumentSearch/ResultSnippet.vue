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
      this.setHTML(newNode);
    }
  },
  mounted () {
    this.setHTML(this.node);
  },
  methods: {
    setHTML (node) {
      this.$refs.snippet.innerHTML = '';
      // Small clean up
      node.querySelectorAll('a').forEach(node => {
        const parent = node.parentNode;
        while (node.firstChild) parent.insertBefore(node.firstChild, node);
        parent.removeChild(node);
      });
      this.$refs.snippet.appendChild(node);
    }
  }
};
</script>

<style scoped>

</style>
