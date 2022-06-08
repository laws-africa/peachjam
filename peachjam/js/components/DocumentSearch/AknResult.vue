<template>
  <div
    class="card"
  >
    <div class="card-body">
      <div>
        <a :href="`#${result.id}`">
          <h5 class="card-title">
            {{ result.title }}
          </h5>
        </a>
      </div>

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
  name: 'AknResult',
  components: { ResultSnippet },
  props: {
    result: {
      type: Object,
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
    markInstance: null,
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
      this.snippets = [...this.result.contentNodes].map(node => {
        return [...node.querySelectorAll('mark')].map(mark => {
          // find nearest akn block element (ensures snippet text)
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
          const originalNode = mark.closest(selector);
          const clonedNode = originalNode.cloneNode(true);
          clonedNode.querySelectorAll('a').forEach(node => {
            const parent = node.parentNode;
            while (node.firstChild) parent.insertBefore(node.firstChild, node);
            parent.removeChild(node);
          });
          return {
            originalNode,
            clonedNode
          };
        });
      }).flat(Infinity);
    }
  }
};
</script>

<style scoped>

</style>
