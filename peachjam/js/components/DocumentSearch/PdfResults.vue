<template>
  <div
    v-for="(snippet, index) in snippets"
    :key="index"
    class="card mb-2"
  >
    <div class="card-body">
      <a
        class="card-title"
        href="#"
        @click.prevent=""
      >
        Page {{ getPageElement(snippet).dataset.page }}
      </a>
      <div>
        {{ snippet.textContent }}
      </div>
      <div>
        <a
          href="#"
          @click.prevent="$emit('go-to-result', snippet);"
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
  props: {
    results: {
      type: Array,
      required: true
    },
    q: {
      type: String,
      required: false,
      default: ''
    }
  },
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
    getPageElement (node) {
      return node.closest('[data-page]');
    },
    renderSnippets () {
      this.snippets = this.results.map(node => {
        const snippet = node.closest('span[role="presentation"]');
        const hello = snippet;
        return snippet;
      });
    }
  }
};
</script>
