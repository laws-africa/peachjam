<template>
  <div>
    <provision-enrichment
      v-for="enrichment in items"
      :key="enrichment.id"
      ref="gutter-item"
      :view-root="viewRoot"
      :enrichment="enrichment"
      :gutter="gutter"
      :use-selectors="useSelectors"
    >
    </provision-enrichment>
  </div>
</template>
<script>
import ProvisionEnrichment from './ProvisionEnrichment.vue';

export default {
  name: 'ProvisionEnrichmentsList',
  components: {
    ProvisionEnrichment
  },
  props: {
    enrichments: {
      type: Array,
      default: () => []
    },
    viewRoot: HTMLElement,
    gutter: HTMLElement,
    useSelectors: Boolean,
    thisWorkFrbrUri: {
      type: String,
      default: ''
    }
  },
  data () {
    return {
      items: this.enrichments,
      creating: null
    };
  }
};
</script>
