<template>
  <la-gutter-item :anchor.prop="anchorElement" class="citation-count">
    <i class="bi bi-speech">💬</i>
    <span class="badge rounded-pill bg-secondary">{{ citations }}</span>
    <div class="card gutter-item-card mt-2">
      <div class="card-body d-flex">
        <span>
          <a :href="`${expressionFrbrUri}/provision/${provision_eid}`">
            Cited {{ citations }} times
          </a>
        </span>
        <button
          type="button"
          class="btn-close ms-auto d-lg-none"
          aria-label="Close"
          @click.stop="deactivate"
        />
      </div>
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
}
</script>
