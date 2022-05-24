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
            v-if="object_document"
            :href="`/documents${object_document.expression_frbr_uri}`"
          >{{ object_document.title }}</a><span v-else>{{ enrichment.object_work_frbr_uri}}</span>.
        </div>
        <div v-else>
          <a
            v-if="subject_document"
            :href="`/documents${subject_document.expression_frbr_uri}`"
          >{{ subject_document.title }}</a><span v-else>{{ enrichment.subject_work_frbr_uri }}</span>.
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

    remove () {
      if (confirm('Are you sure?')) {
        this.$emit('delete', this.enrichment);
      }
    }
  }
};
</script>
