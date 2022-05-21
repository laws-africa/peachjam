<template>
  <div>
    <relationship-enrichment
      v-for="(enrichment) in enrichments"
      :key="enrichment.id"
      ref="gutter-item"
      :enrichment="enrichment"
      :view-root="viewRoot"
      :gutter="gutter"
      :readonly="readonly"
      :this-work-frbr-uri="thisWorkFrbrUri"
      @edit="edit"
    />
    <relationship-enrichment-modal
      v-if="editing"
      :enrichment="editing"
      @delete="deleteEnrichment"
      @save="saveEdits"
      @close="closeModal"
    />
  </div>
</template>

<script>
import RelationshipEnrichment from './RelationshipEnrichment.vue';
import RelationshipEnrichmentModal from './RelationshipEnrichmentModal.vue';

export default {
  name: 'RelationshipEnrichmentList',
  components: {
    RelationshipEnrichmentModal,
    RelationshipEnrichment
  },
  props: {
    enrichments: {
      type: Array,
      default: []
    },
    viewRoot: HTMLElement,
    gutter: HTMLElement,
    readonly: Boolean,
    thisWorkFrbrUri: {
      type: String,
      default: ''
    }
  },
  data: () => {
    return {
      editing: null
    };
  },
  methods: {
    markAndAnchorAll () {
      if (this.$refs['gutter-item']) {
        this.$refs['gutter-item'].forEach(item => {
          item.markAndAnchor();
        });
      }
    },

    edit (enrichment) {
      this.editing = enrichment;
    },

    deleteEnrichment () {
      // TODO: delete from the server

      const ix = this.enrichments.findIndex((e) => e.id === this.editing.id);
      if (ix > -1) {
        // eslint-disable-next-line vue/no-mutating-props
        this.enrichments.splice(ix, 1);
      }
      this.editing = null;
    },

    saveEdits (enrichment) {
      if (enrichment.id) {
        // TODO: save to server
        console.log('saving');
      } else {
        // it's new
        // TODO: save to server
        this.enrichments.push(enrichment);
      }
      this.editing = null;
    },

    closeModal () {
      this.editing = null;
    }
  }
};
</script>
