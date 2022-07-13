<template>
  <div class="">
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
        <h5 class="card-title">
          <strong>{{ snippet.titleNode.textContent }}</strong>
        </h5>
        <ResultSnippet
          :node="snippet.snippetNode.cloneNode(true)"
        />
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
      const nodes = this.nodes.map(node => {
        const aknSelectors = [
          'blockContainer',
          'block',
          'blockList',
          'conclusions',
          'foreign',
          'heading',
          'subheading',
          'listIntroduction',
          'listWrapUp',
          'intro',
          'wrapUp',
          'crossHeading',
          'item',
          'ol',
          'p',
          'preface',
          'tblock',
          'toc',
          'ul'
        ].map(item => `.akn-${item}`);
        const selector = ['h1', 'h2', 'h3', 'h4', 'h5', ...aknSelectors].join(', ');
        const snippetNode = node.closest(selector);
        return snippetNode ? node.closest(selector) : node;
      });
      nodes.forEach(node => { set.add(node); });
      this.snippets = [...set].map(node => {
        let titleNode; let ancestor = node;
        const findTitle = () => {
          ancestor = ancestor.parentElement;
          const target = ancestor.querySelector('h1, h2, h3, h4, h5, .akn-heading, .akn-subheading');
          if (target) {
            titleNode = target;
          } else {
            findTitle();
          }
        };
        findTitle();
        return {
          snippetNode: node,
          titleNode
        };
      });
    }
  }
};
</script>
