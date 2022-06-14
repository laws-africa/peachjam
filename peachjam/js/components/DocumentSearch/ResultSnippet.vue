<template>
  <div
    ref="snippet"
    class="snippet"
  />
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
      // Anchor clean up
      node.querySelectorAll('a').forEach(node => {
        const parent = node.parentNode;
        while (node.firstChild) parent.insertBefore(node.firstChild, node);
        parent.removeChild(node);
      });
      // Inline style clean up
      node.removeAttribute('style');
      node.querySelectorAll('*').forEach(node => node.removeAttribute('style'));
      this.$refs.snippet.appendChild(node);
    }
  }
};
</script>

<style scoped>
.snippet > * {
  font-family: 'Lato', sans-serif !important;
  font-size: 16px !important;
}
</style>
