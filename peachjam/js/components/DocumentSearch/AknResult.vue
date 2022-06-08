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
          :node="snippet"
        />
        <div>
          <a
            href="#"
            @click.prevent="handleResultClick(snippet)"
          >
            Go to section
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
import Mark from 'mark.js';
import ResultSnippet from './ResultSnippet.vue';

export default {
  name: 'AknResult',
  components: { ResultSnippet },
  props: {
    q: {
      type: String,
      default: ''
    },
    result: {
      type: Object,
      required: true
    }
  },
  emits: ['mark-clicked'],
  data: () => ({
    markInstance: null,
    snippets: []
  }),

  watch: {
    q: {
      handler (value) {
        this.mark(value);
      }
    }
  },

  mounted () {
    this.mark(this.q);
  },

  methods: {
    mark (q) {
      const markInstance = new Mark(this.result.contentNodes);
      markInstance.unmark();
      markInstance.mark(q, {
        separateWordSearch: false
      });
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
          const snippetNode = mark.closest(selector);
          const clonedNode = snippetNode.cloneNode(true);
          clonedNode.querySelectorAll('a').forEach(node => {
            const parent = node.parentNode;
            while (node.firstChild) parent.insertBefore(node.firstChild, node);
            parent.removeChild(node);
          });
          return clonedNode;
        });
      }).flat(Infinity);
    },
    handleResultClick (node) {
      this.$emit('mark-clicked', `[data-eid="${node.getAttribute('data-eid')}"]`);
    }
  }
};
</script>

<style scoped>

</style>
