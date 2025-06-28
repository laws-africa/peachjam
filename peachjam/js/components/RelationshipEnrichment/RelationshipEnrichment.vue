<template>
  <la-gutter-item
    class="relationship-gutter-item"
    :anchor.prop="anchorElement"
    @click="activate"
  >
    <i class="bi bi-chat-left mobile-gutter-item-icon" />
    <div class="card">
      <div class="card-body">
        <div class="mb-2 d-lg-none text-end">
          <button
            type="button"
            class="btn-close"
            aria-label="Close"
            @click.stop="deactivate"
          />
        </div>

        <div
          v-if="editable"
          class="float-end d-none d-lg-block"
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
                  {{ $t('Delete') }}
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div v-if="isForwards">
          {{ $t('This provision') }}
          {{ enrichment.predicate.verb }}
          <a
            v-if="objectDocument"
            target="_blank"
            :href="`${objectDocument.expression_frbr_uri}/`"
          >{{ objectDocument.title }}</a><span v-else>{{ enrichment.object_work.frbr_uri }} xx</span>.
        </div>
        <div v-else>
          <a
            v-if="subjectDocument"
            target="_blank"
            :href="`${subjectDocument.expression_frbr_uri}/`"
          >{{ subjectDocument.title }}</a><span v-else>{{ enrichment.subject_work.frbr_uri }}</span>.
          {{ $t('{reverse_verb} this provision', { reverse_verb: enrichment.predicate.reverse_verb }) }}.
        </div>
      </div>
    </div>
  </la-gutter-item>
</template>

<script>
import { markRange, targetToRange } from '@lawsafrica/indigo-akn/dist/ranges';
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
    editable: Boolean,
    useSelectors: Boolean,
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
    window.addEventListener('click', this.handleOutsideClick);

    this.gutter.appendChild(this.$el);
  },

  unmounted () {
    this.unmark();
  },

  beforeUnmount () {
    // clean up
    window.removeEventListener('click', this.handleOutsideClick);
    this.marks.forEach(mark => {
      mark.removeEventListener('click', mark.clickFn);
    });
  },

  methods: {
    handleOutsideClick (e) {
      if (!(this.$el.contains(e.target) ||
          this.$el === e.target ||
          this.marks.some(mark => mark.contains(e.target) || mark === e.target))) {
        this.deactivate();
      }
    },
    deactivate () {
      this.$el.active = false;
      this.marks.forEach(mark => mark.classList.remove('active'));
    },
    activate () {
      // Deactivate all
      Array.from(this.viewRoot.querySelectorAll('mark')).forEach(mark => {
        mark.classList.remove('active');
      });
      // Activate gutter item
      this.$el.active = true;
      // activate enrichment gutter item marks
      this.marks.forEach(mark => {
        mark.classList.add('active');
      });
    },
    markAndAnchor () {
      this.unmark();
      const target = {
        anchor_id: this.isForwards ? this.enrichment.subject_target_id : this.enrichment.object_target_id,
        selectors: this.useSelectors ? (
          this.isForwards ? this.enrichment.subject_selectors : this.enrichment.target_selectors
        ) : null
      };
      const range = targetToRange(target, this.viewRoot);
      if (!range) return;
      markRange(range, 'mark', mark => {
        this.marks.push(mark);
        mark.classList.add('enrich-relationship');
        mark.clickFn = () => this.activate();
        // Setup listeners
        mark.addEventListener('click', mark.clickFn);
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

<style scoped>

.bi-chat-left {
  text-align: center;
  position: relative;
  z-index: 9;
}

@media screen and (max-width: 992px) {
  .card {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    transform: translateY(100%);
    transition: transform ease-in-out 300ms;
    z-index: 9;
  }

  la-gutter-item[active] {
    z-index: 9;
  }

  la-gutter-item[active] .card {
    transform: translateY(0);
  }

  /*So content is above To the top element*/
  .card .card-body {
    padding-bottom: 40px;
  }
}
</style>
