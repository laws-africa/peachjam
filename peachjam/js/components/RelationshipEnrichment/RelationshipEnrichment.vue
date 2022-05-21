<template>
  <la-gutter-item :anchor.prop="anchorElement">
    <div class="card">
      <div class="card-body">
        <p v-if="isForwards">
          This provision
          {{ enrichment.predicate.verb }}
          <a :href="`/documents${object_document.expression_frbr_uri}`">{{ object_document.title }}</a>.
        </p>
        <p v-else>
          <a :href="`/documents${subject_document.expression_frbr_uri}`">{{ subject_document.title }}</a>.
          {{ enrichment.predicate.reverse_verb }}
          this provision.
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
import { bestDocument } from './enrichment';

export default {
  name: 'RelationshipEnrichment',
  props: {
    enrichment: {
      type: Object,
      default: null
    },
    viewRoot: HTMLElement,
    gutter: HTMLElement,
    readonly: Boolean,
    thisWorkFrbrUri: {
      type: String,
      default: ''
    }
  },
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

  computed: {
    isForwards () {
      return this.enrichment.subject_work_frbr_uri === this.thisWorkFrbrUri;
    },

    object_document () {
      return bestDocument(this.enrichment.object_documents, 'eng');
    },

    subject_document () {
      return bestDocument(this.enrichment.subject_documents, 'eng');
    }
  },

  methods: {
    markAndAnchor () {
      this.unmark();
      const target = {
        anchor_id: this.isForwards ? this.enrichment.subject_target_id : this.enrichment.object_target_id
      };
      const range = targetToRange(target, this.viewRoot);
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
