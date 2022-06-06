<template>
  <div
    class="card"
  >
    <div class="card-body">
      <a :href="`#${result.id}`">
        <h5 class="card-title">
          {{ result.title }}
        </h5>
      </a>
      <div
        v-show="false"
        ref="content"
        class="card-text"
      >
        {{ result.content }}
      </div>
      <p ref="result-snippet" />
    </div>
  </div>
</template>

<script>
import Mark from 'mark.js';

export default {
  name: 'ResultCard',
  props: {
    q: {
      type: String,
      default: ''
    },
    result: {
      type: Object,
      default: () => ({
        title: '',
        content: ''
      })
    }
  },
  emits: ['mark-clicked'],
  data: () => ({
    markInstance: null
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
      const instance = new Mark(this.$refs.content);
      instance.unmark();
      instance.mark(q, {
        separateWordSearch: false
      });
      this.$refs['result-snippet'].innerHTML = '';
      const childNodes = [...this.$refs.content.childNodes];
      childNodes.forEach((node, index) => {
        let markCounter = 0;
        // if mark element next include textNode
        const nextNodeIsMark = index < childNodes.length - 1 && childNodes[index + 1].nodeName === 'MARK';
        const clonedNode = node.cloneNode(true);
        if (clonedNode.nodeType === 3 && nextNodeIsMark) {
          const words = clonedNode.nodeValue.split(' ');
          clonedNode.nodeValue = `...${words.length > 13 ? words.slice(words.length - 7, words.length - 1).join(' ') : words.join(' ')}`;
          this.$refs['result-snippet'].appendChild(clonedNode);
        } else if (clonedNode.nodeName === 'MARK') {
          markCounter++;
          clonedNode.setAttribute('count', markCounter);
          clonedNode.setAttribute('role', 'button');
          const brElement = document.createElement('br');
          clonedNode.appendChild(brElement);
          clonedNode.addEventListener('click', (e) => {
            this.$emit('mark-clicked', {
              sectionId: this.result.id,
              nthMark: e.currentTarget.getAttribute('count')
            });
          });
          this.$refs['result-snippet'].appendChild(clonedNode);
        }
      });
    }
  }
};
</script>

<style scoped>

</style>
