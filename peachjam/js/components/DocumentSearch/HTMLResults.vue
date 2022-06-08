<template>
  <div class="card">
    <div class="card-body">
      <div
        v-for="(snippet, index) in snippets"
        :key="index"
      >
        <ResultSnippet
          class="mb-2"
          :node="snippet.clonedNode"
        />
        <div>
          <a
            href="#"
            @click.prevent="$emit('go-to-result', snippet.originalNode);"
          >
            Go to result
          </a>
        </div>
        <hr
          v-if="index < snippets.length -1"
          class="mb-2"
        >
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
          originalNode: snippet,
          clonedNode: snippet.cloneNode(true)
        });
      });
    }
  }
};
</script>

<style scoped>

</style>
