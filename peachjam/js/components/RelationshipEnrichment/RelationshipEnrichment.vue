<template>
  <la-gutter-item :anchor.prop="anchorElement">
    <div class="card">
      <div class="card-body">
        <p>
          {{ enrichment.title }}
        </p>
        <div v-if="!readonly">
          <button type="button" class="btn btn-sm btn-primary" @click="edit">Edit</button>
        </div>
      </div>
    </div>
  </la-gutter-item>
</template>

<script>
import { markRange, targetToRange } from '@laws-africa/indigo-akn/dist/ranges';

export default {
  name: 'RelationshipEnrichment',
  props: ['enrichment', 'viewRoot', 'gutter', 'readonly'],
  data: () => ({
    marks: [],
    anchorElement: null
  }),

  mounted () {
    this.markAndAnchor();
    this.gutter.appendChild(this.$el);
  },

  unmounted () {
    this.unmark();
  },

  methods: {
    markAndAnchor () {
      this.unmark();
      if (!this.enrichment.target) return;
      const range = targetToRange(this.enrichment.target, this.viewRoot);
      if (!range) return;
      markRange(range, 'mark', mark => {
        this.marks.push(mark);
        return mark;
      });
      this.anchorElement = this.marks[0];
    },

    unmark () {
      this.marks.forEach(mark => {
        const parent = mark.parentNode;
        while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
        parent.removeChild(mark);
      });
      this.marks = [];
    },

    edit () {
      this.$emit('edit', this.enrichment);
    }
  }
};
</script>
