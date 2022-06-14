<template>
  <div>
    <div
      v-for="(snippet, index) in snippets"
      :key="index"
      class="card"
    >
      <div class="card-body">
        <div v-if="snippet.titleNode">
          <a :href="`#${snippet.titleNode.id}`">
            <h5 class="card-title">
              {{ snippet.titleNode.textContent }}
            </h5>
          </a>
        </div>

        <ResultSnippet
          class="mb-2"
          :node="snippet.snippetNode.cloneNode(true)"
        />
        <div>
          <a
            href="#"
            @click.prevent="$emit('go-to-snippet', snippet.snippetNode);"
          >
            Go to result
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import ResultSnippet from './ResultSnippet.vue';

export default {
  name: 'AknSnippets',
  components: { ResultSnippet },
  props: {
    nodes: {
      type: Array,
      required: true
    }
  },
  emits: ['go-to-snippet'],
  data: () => ({
    markInstance: null,
    snippets: []
  }),

  watch: {
    nodes: {
      deep: true,
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
      const nodeSet = new Set();
      this.nodes.forEach(node => {
        nodeSet.add(node);
      });
      this.snippets = [...nodeSet].map(node => {
        const titleNode = node.closest('.akn-section') ? node.closest('.akn-section').querySelector('h3') : '';
        const selector = [
          'blockContainer',
          'block',
          'blockList',
          'conclusions',
          'foreign',
          'item',
          'ol',
          'p',
          'preface',
          'tblock',
          'toc',
          'ul'
        ].map(item => `.akn-${item}`).join(', ');
        const snippet = node.closest(selector);
        return {
          titleNode,
          snippetNode: snippet ? node.closest(selector) : node
        };
      });
    }
  }
};
</script>
