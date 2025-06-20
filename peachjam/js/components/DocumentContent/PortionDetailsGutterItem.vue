<template>
  <la-gutter-item :anchor.prop="anchorElement">
    <div
      v-if="provisionEid"
      class="gutter-enrichment-active-portion btn-group-vertical bg-white"
    >
      <a
        class="btn btn-outline-secondary"
        :href="compareUrl"
      >
        <i class="bi bi-book"></i>
        {{ $t('Compare...') }}
      </a>
      <a
        class="btn btn-outline-secondary"
        :href="similarUrl"
      >
        <i class="bi bi-intersect"></i>
        {{ $t('Similar provisions...') }}
      </a>
    </div>
  </la-gutter-item>
</template>

<script>
import peachjam from '../../peachjam';

export default {
  name: 'PortionDetailsGutterItem',
  props: {
    baseUrl: {
      type: String,
      required: true
    },
    expressionFrbrUri: {
      type: String,
      required: true
    }
  },
  data: () => ({
    anchorElement: null,
    provisionEid: null
  }),
  computed: {
    compareUrl () {
      return `${peachjam.config.urlLangPrefix}/compare?uri-a=${encodeURIComponent(this.expressionFrbrUri)}/~${this.provisionEid}`;
    },
    similarUrl () {
      return `${this.baseUrl}/provision/${this.provisionEid}/similar`;
    }
  },
  methods: {
    setActiveElement (element) {
      this.anchorElement = element;
      this.provisionEid = element?.getAttribute('data-eid') || null;
    },
    deactivate () {
      this.$el.active = false;
      this.setActiveElement(null);
    }
  }
};
</script>
