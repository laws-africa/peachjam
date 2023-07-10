<template>
  <la-gutter-item :anchor.prop="anchorElement">
    <div class="card">
      <div class="card-body">
        <p>
          <button class="btn btn-sm btn-outline-secondary float-end ms-1" @click="edit">
            {{ $t('Edit') }}
          </button>
          {{ link.text }}
          <br>
          <a :href="link.url" target="_blank">{{ link.url }}</a>
        </p>
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
