<template>
  <li class="mb-4 hit">
    <a
      class="h5"
      target="_blank"
      rel="noreferrer"
      :href="`${item.expression_frbr_uri}?q=${encodeURIComponent(query)}`"
    >
      {{ item.title }}
    </a>
    <div>
      {{ item.matter_type }}
    </div>
    <div>
      <i>{{ item.citation }}</i>
    </div>
    <div class="text-muted">
      {{ item.date }} <span class="ms-3">{{ item.doc_type }}</span>
      <span
        v-if="item.court"
        class="ms-3"
      >{{ item.court }}</span>
      <span
        v-if="item.author"
        class="ms-3"
      >{{ item.author }}</span>
    </div>
    <div class="text-muted">
      {{ item.jurisdiction }}
      <span v-if="item.locality">· {{ item.locality }}</span>
    </div>
    <div v-if="item.pages.length">
      <div
        v-for="(page, index) in item.pages"
        :key="index"
      >
        <span>
          <a :href="`${item.expression_frbr_uri}?q=${encodeURIComponent(query)}&page=${page.page_num}`">Page {{ page.page_num }}</a>:
        </span>
        <span v-html="page.highlight['pages.body'].join(' ... ')" />
      </div>
    </div>
    <div v-else>
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
    },
    query: {
      type: String,
      default: () => ''
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
