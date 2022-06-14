<template>
  <div>
    <div
      v-for="(snippet, index) in snippets"
      :key="index"
      class="card"
    >
      <div class="card-body">
        <div v-if="snippet.titleNode && snippet.sectionId">
          <a :href="`#${snippet.sectionId}`">
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
      const set = new Set();
      const nodes = this.nodes.map(node => {
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
        const snippetNode = node.closest(selector);
        return snippetNode ? node.closest(selector) : node;
      });
      nodes.forEach(node => { set.add(node); });
      this.snippets = [...set].map(node => {
        const section = node.closest('.akn-section');
        return {
          snippetNode: node,
          sectionId: section ? section.id : '',
          titleNode: section ? section.querySelector('h3') : ''
        };
      });
    }
  }
};
</script>
