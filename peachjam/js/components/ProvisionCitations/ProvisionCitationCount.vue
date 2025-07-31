<template>
  <la-gutter-item :anchor.prop="anchorElement" class="citation-count">
    <div class="">
      <span class="align-middle me-2 fs-5"><i class="bi bi-chat-quote" /></span>
      <span class="badge rounded-pill bg-secondary">{{ citations }}</span>
      <span class="gutter-item-link ms-2 border p-2 rounded bg-white d-inline-flex justify-content-around">
        <a :href="`${expressionFrbrUri}/provision/${provision_eid}`">
          {{ $t('Cited {count} times', {count: citations}) }}
        </a>
       <button
          type="button"
          class="btn-close ms-auto d-lg-none"
          aria-label="Close"
          @click.stop="deactivate"
        />
      </span>
    </div>
  </la-gutter-item>
</template>

<script>
export default {
  name: 'IncomingCitationCount',
  props: ['provision_eid', 'citations', 'expressionFrbrUri', 'gutter'],
  data: () => ({
    anchorElement: null
  }),
  mounted () {
    this.setAnchor();
    // this can't be attached with vue's normal event listener because of the naming
    this.$el.addEventListener('laItemChanged', this.itemChanged);
    this.gutter.appendChild(this.$el);
  },
  methods: {
    itemChanged () {
      // either the active or anchor state has changed
      if (this.$el.active) {
        this.activate();
      } else {
        this.deactivate();
      }
    },
    setAnchor () {
      this.anchorElement = document.querySelector(`[data-eid="${this.provision_eid}"`);
      if (this.anchorElement) {
        this.anchorElement.classList.add('enrich', 'enrich-citation-count');
      }
    },
    activate () {
      this.$el.active = true;
      this.anchorElement.classList.add('active');
    },
    deactivate () {
      this.$el.active = false;
      this.anchorElement.classList.remove('active');
    }
  }
};
</script>
