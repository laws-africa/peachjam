<template>
  <la-gutter-item :anchor.prop="anchorElement">
    <i
      class="bi bi-link mobile-gutter-item-icon"
      role="button"
      @click="activate"
    />
    <div class="card gutter-item-card">
      <div class="card-body">
        <div>
          <button class="btn btn-sm btn-outline-secondary float-end ms-1" @click="edit">
            {{ $t('Edit') }}
          </button>
          {{ link.text }}
        </div>
        <div>
          <a :href="link.url" target="_blank">
            {{ link.url }}
            <span
              v-if="link.is_external"
              class="visually-hidden"
            >
              {{ $t('opens in new tab') }}
            </span>
          </a>
          <span
            v-if="link.is_external"
            class="badge bg-secondary ms-2"
          >
            {{ $t('External') }}
            <i
              class="bi bi-box-arrow-up-right ms-1"
              :title="$t('External document')"
              aria-hidden="true"
            />
          </span>
        </div>
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
