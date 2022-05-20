<template>
  <li class="mb-4 hit">
    <a
      class="h5"
      target="_blank"
      rel="noreferrer"
      :href="item.work_frbr_uri"
    >
      {{ item.title }}
    </a>
    <div>
      {{ item.matter_type }}
    </div>
    <div>
      {{ item.citation }}
    </div>
    <div>
      <span v-if="item.authoring_body"><strong>{{ item.authoring_body }}</strong> - </span>
      <span class="text-muted">{{ item.date }}</span>
    </div>
    <div>
      {{ item.jurisdiction }}
    </div>
    <div>
      <span
        class="snippet"
        v-html="highlights(item)"
      />
    </div>
  </li>
</template>

<script>
export default {
  name: 'SearchResult',
  props: {
    item: {
      type: Object,
      default () {
        return {};
      }
    }
  },
  methods: {
    highlights (item) {
      if (item.highlight.content) {
        return item.highlight.content.join(' ... ');
      }
    }
  }
};
</script>

<style>
.hit mark {
  font-weight: bold;
  padding: 0px;
}
.snippet {
  line-height: 1.3;
  word-break: break-word;
}
</style>
