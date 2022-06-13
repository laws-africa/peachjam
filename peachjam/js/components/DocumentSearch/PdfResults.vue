<template>
  <div
    v-for="(snippet, index) in snippets"
    :key="index"
    class="card mb-2"
  >
    <div class="card-body">
      <div class="card-title">
        <strong>
          Page {{ getPageTitle(snippet.nodeForClickFn) }}
        </strong>
      </div>
      <div>
        {{ snippet.text }}
      </div>
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
export default {
  name: 'PdfResults',
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
    getPageTitle (node) {
      return node.closest('[data-page]').dataset.page;
    },
    renderSnippets () {
      this.snippets = this.results.map(node => {
        const snippet = node.closest('span[role="presentation"]');
        return ({
          nodeForClickFn: snippet,
          text: snippet.textContent
        });
      });
    }
  }
};
</script>
