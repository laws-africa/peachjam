<template>
  <div>
    <relationship-enrichment
      v-for="enrichment in items"
      :key="enrichment.id"
      ref="gutter-item"
      :enrichment="enrichment"
      :view-root="viewRoot"
      :gutter="gutter"
      :readonly="readonly"
      :this-work-frbr-uri="thisWorkFrbrUri"
      @delete="deleteEnrichment(enrichment)"
    />
    <relationship-enrichment-modal
      v-if="creating"
      :enrichment="creating"
      @save="save"
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
      default: () => []
    },
    viewRoot: HTMLElement,
    gutter: HTMLElement,
    readonly: Boolean,
    thisWorkFrbrUri: {
      type: String,
      default: ''
    }
  },
  data: (x) => {
    return {
      items: x.enrichments,
      creating: null
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

    deleteEnrichment (enrichment) {
      // TODO: delete from the server
      const ix = this.items.findIndex((e) => e.id === enrichment.id);
      if (ix > -1) {
        // eslint-disable-next-line vue/no-mutating-props
        this.items.splice(ix, 1);
      }
    },

    save (enrichment) {
      // TODO: save to server
      this.items.push(enrichment);
      this.creating = null;
    },

    closeModal () {
      this.creating = null;
    }
  }
};
</script>
