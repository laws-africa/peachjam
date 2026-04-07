<template>
  <la-gutter-item :anchor.prop="anchorElement">
    <i
      class="`bi bi-link mobile-gutter-item-icon"
      role="button"
      @click="activate"
    />
    <div class="card gutter-item-card">
      <div class="card-body">
        <p>
          <button class="btn btn-sm btn-outline-secondary float-end ms-1" @click="edit">
            {{ $t('Edit') }}
          </button>
          {{ link.text }}
          <br>
          <a
            :href="link.url"
          >
            {{ link.url }}
            <span
              v-if="link.is_external"
              class="ms-1 text-muted"
            >
              ({{ $t('External') }})
            </span>
            <i
              v-if="link.is_external"
              class="bi bi-box-arrow-up-right ms-1"
              :title="$t('External document')"
              aria-hidden="true"
            />
          </a>
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
    },
    activate () {
      this.$el.active = true;
    }
  }
};
</script>
