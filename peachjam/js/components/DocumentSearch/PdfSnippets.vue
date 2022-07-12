<template>
  <div
    v-for="(snippet, index) in snippets"
    :key="index"
    class="card snippet-card mb-2"
    :tabindex="index"
    role="button"
    aria-pressed="false"
    @click="$emit('go-to-snippet', snippet.snippetNode);"
  >
    <div class="card-body">
      <h5><strong>{{ $t("Page") }} {{ snippet.pageNode.dataset.page }}</strong></h5>
      <div>
        <ResultSnippet :node="snippet.snippetNode.cloneNode(true)" />
      </div>
    </div>
  </div>
</template>

<script>
import ResultSnippet from './ResultSnippet.vue';
export default {
  name: 'PdfSnippets',
  components: { ResultSnippet },
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
      const nodes = this.nodes.map(node => node.closest('span[role="presentation"]'));
      nodes.forEach(node => {
        set.add(node);
      });
      this.snippets = [...set].map(node => ({
        snippetNode: node,
        pageNode: node.closest('[data-page]')
      }));
    }
  }
};
</script>
