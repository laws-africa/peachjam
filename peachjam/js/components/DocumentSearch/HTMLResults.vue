<template>
  <div
    v-for="(snippet, index) in snippets"
    :key="index"
    class="card mb-2"
  >
    <div class="card-body">
      <ResultSnippet
        class="mb-2"
        :node="snippet.node"
      />
      <div>
        <a
          href="#"
          @click.prevent="$emit('go-to-result', snippet.nodeForClickFn);"
        >
          Go to result
        </a>
      </div>
    </div>
  </div>
</template>

<script>
import ResultSnippet from './ResultSnippet.vue';
export default {
  name: 'HTMLResults',
  components: {
    ResultSnippet
  },
  props: ['results', 'q'],
  emits: ['go-to-result'],
  data: () => ({
    snippets: []
  }),
  watch: {
    q: {
      handler () {
        this.renderSnippets();
      }
    }
  },

  mounted () {
    this.renderSnippets();
  },
  methods: {
    renderSnippets () {
      this.snippets = this.results.map(node => {
        const snippet = node.closest('p, h1, h2, h3, h4, h5, h6, address, blockquote, div, table');
        return ({
          nodeForClickFn: snippet,
          node: snippet.cloneNode(true)
        });
      });
    }
  }
};
</script>

<style scoped>

</style>
