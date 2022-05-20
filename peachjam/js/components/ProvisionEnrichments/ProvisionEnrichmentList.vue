<template>
  <div>
    <provision-enrichment
      v-for="(enrichment) in enrichments"
      :key="key(enrichment)"
      ref="gutter-item"
      :enrichment="enrichment"
      :view-root="viewRoot"
      :gutter="gutter"
    />
  </div>
</template>

<script>
import ProvisionEnrichment from './ProvisionEnrichment.vue';
let counter = -1;

export default {
  name: 'ProvisionEnrichmentList',
  components: {
    ProvisionEnrichment
  },
  props: ['gutter', 'viewRoot', 'enrichments'],
  methods: {
    key (enrichment) {
      if (enrichment.id) {
        return enrichment.id;
      }
      if (!enrichment._id) {
        enrichment._id = --counter;
      }
      return enrichment._id;
    },

    markAndAnchorAll () {
      if (this.$refs['gutter-item']) {
        this.$refs['gutter-item'].forEach(item => {
          item.markAndAnchor();
        });
      }
    }
  }
};
</script>
