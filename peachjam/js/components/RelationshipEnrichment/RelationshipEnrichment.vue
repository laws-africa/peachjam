<template>
  <la-gutter-item :anchor.prop="anchorElement">
    <div class="card">
      <div class="card-body">
        <div
          v-if="!readonly"
          class="float-end"
        >
          <div class="dropdown">
            <a
              class="dropdown-toggle"
              href="#"
              data-bs-toggle="dropdown"
            />
            <ul class="dropdown-menu">
              <li>
                <a
                  class="dropdown-item"
                  href="#"
                  @click.prevent="remove"
                >
                  Delete
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div v-if="isForwards">
          This provision
          {{ enrichment.predicate.verb }}
          <a
            v-if="objectDocument"
            :href="`/documents${objectDocument.expression_frbr_uri}`"
          >{{ objectDocument.title }}</a><span v-else>{{ enrichment.object_work.frbr_uri }} xx</span>.
        </div>
        <div v-else>
          <a
            v-if="subjectDocument"
            :href="`/documents${subjectDocument.expression_frbr_uri}`"
          >{{ subjectDocument.title }}</a><span v-else>{{ enrichment.subject_work.frbr_uri }}</span>.
          {{ enrichment.predicate.reverse_verb }}
          this provision.
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
  emits: ['delete'],
  data: () => ({
    marks: [],
    anchorElement: null
  }),

  computed: {
    isForwards () {
      return this.enrichment.subject_work.frbr_uri === this.thisWorkFrbrUri;
    },

    objectDocument () {
      return bestDocument(this.enrichment.object_documents, 'eng');
    },

    subjectDocument () {
      return bestDocument(this.enrichment.subject_documents, 'eng');
    }
  },

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

    remove () {
      if (confirm('Are you sure?')) {
        this.$emit('delete', this.enrichment);
      }
    }
  }
};
</script>
