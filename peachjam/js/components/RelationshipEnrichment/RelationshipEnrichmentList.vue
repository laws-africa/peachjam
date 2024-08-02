<template>
  <div>
    <relationship-enrichment
      v-for="enrichment in items"
      :key="enrichment.id"
      ref="gutter-item"
      :enrichment="enrichment"
      :view-root="viewRoot"
      :gutter="gutter"
      :editable="editable"
      :use-selectors="useSelectors"
      :this-work-frbr-uri="thisWorkFrbrUri"
      @delete="deleteEnrichment(enrichment)"
    />
    <relationship-enrichment-modal
      v-if="creating"
      :enrichment="creating"
      :this-work-frbr-uri="thisWorkFrbrUri"
      @save="save"
      @close="closeModal"
    />
  </div>
</template>

<script>
import RelationshipEnrichment from './RelationshipEnrichment.vue';
import RelationshipEnrichmentModal from './RelationshipEnrichmentModal.vue';
import { authHeaders } from '../../api';

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
    editable: Boolean,
    useSelectors: Boolean,
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

    async deleteEnrichment (enrichment) {
      const resp = await fetch(`/api/relationships/${enrichment.id}/`, {
        method: 'DELETE',
        headers: await authHeaders()
      });
      if (resp.ok) {
        const ix = this.items.findIndex((e) => e.id === enrichment.id);
        if (ix > -1) {
          // eslint-disable-next-line vue/no-mutating-props
          this.items.splice(ix, 1);
        }
      }
    },

    async save (enrichment) {
      const headers = await authHeaders();
      headers['Content-Type'] = 'application/json';

      const resp = await fetch('/api/relationships/', {
        method: 'POST',
        headers,
        body: JSON.stringify(enrichment)
      });
      if (resp.ok) {
        this.items.push(await resp.json());
        this.creating = null;
      }
    },

    closeModal () {
      this.creating = null;
    }
  }
};
</script>
