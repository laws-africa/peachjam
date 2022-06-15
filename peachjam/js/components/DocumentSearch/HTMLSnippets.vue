<template>
  <div
    v-for="(snippet, index) in snippets"
    :key="index"
    class="card mb-2"
  >
    <div class="card-body">
      <ResultSnippet
        class="mb-2"
        :node="snippet.cloneNode(true)"
      />
      <div>
        <a
          href="#"
          @click.prevent="$emit('go-to-snippet', snippet);"
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
  name: 'HTMLSnippets',
  components: {
    ResultSnippet
  },
  props: {
    nodes: {
      type: Array,
      required: true
    }
  },
  emits: ['go-to-snippet'],
  data: () => ({
    snippets: []
  }),
  watch: {
    nodes () {
      this.renderSnippets();
    }
  },

  mounted () {
    this.renderSnippets();
  },
  methods: {
    renderSnippets () {
      const set = new Set();
      const nodes = this.nodes.map(node => node.closest('p, h1, h2, h3, h4, h5, h6, address, blockquote, div, table'));
      nodes.forEach(node => set.add(node));
      this.snippets = [...set];
    }
  }
};
</script>
