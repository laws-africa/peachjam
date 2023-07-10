<template>
  <la-gutter-item :anchor.prop="anchorElement">
    <div class="card">
      <div class="card-body">
        <p>
          {{ link.text }}
          <br>
          <a :href="link.url" target="_blank">{{ link.url }}</a>
        </p>
        <button class="btn btn-sm btn-outline-secondary" @click="edit">
          {{ $t('Edit') }}
        </button>
      </div>
    </div>
  </la-gutter-item>
</template>

<script>
export default {
  name: 'CitationLinkGutterItem',
  props: {
    link: {
      type: Object,
      default: null
    },
    anchorElement: {
      type: HTMLElement,
      default: null
    },
    provider: {
      type: Object,
      default: null
    }
  },

  methods: {
    edit () {
      this.provider.editLink(this.link);
    }
  }
};
</script>
