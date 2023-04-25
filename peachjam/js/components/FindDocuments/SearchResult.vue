<template>
  <li class="mb-4 hit">
    <a
      class="h5"
      target="_blank"
      rel="noreferrer"
      :href="item.expression_frbr_uri"
    >
      {{ item.title }}
    </a>
    <div>
      {{ item.matter_type }}
    </div>
    <div v-if="item.citation && item.citation !== item.title">
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
      <span v-html="getFlag(item.jurisdiction)"></span>
      {{ item.jurisdiction }}
      <span v-if="item.locality">· {{ item.locality }}</span>
    </div>



    <div v-if="item.pages.length">
      <div
        v-for="(page, index) in item.pages"
        :key="index"
      >
        <span>
          <a :href="`${item.expression_frbr_uri}?page=${page.page_num}`">Page {{ page.page_num }}</a>:
        </span>
        <span v-if="page.highlight['pages.body']" v-html="page.highlight['pages.body'].join(' ... ')" />
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
    },
    getFlag (jurisdiction) {
      const flagEmojiCodes = {
        Ghana: '&#127468;&#127469;',
        'South Africa': '&#127487;&#127462;',
        Lesotho: '&#127473;&#127480;',
        Malawi: '&#127474;&#127484;',
        Namibia: '&#127475;&#127462;',
        Senegal: '&#127480;&#127475;',
        Seychelles: '&#127480;&#127464;',
        'Sierra Leone': '&#127480;&#127473;',
        Tanzania: '&#127481;&#127487;',
        'Turks and Caicos Islands': '&#127481;&#127464;',
        Uganda: '&#127482;&#127468;',
        Zambia: '&#127487;&#127474;',
        Zanzibar: '&#127481;&#127487;',
        Zimbabwe: '&#127487;&#127484;',
        'African Regional Bodies': '<img style="width:19px;margin-bottom:4px; margin-right:1px" alt="African Union Icon"  src="/static/images/au_icon.png" />'
      };
      return flagEmojiCodes[jurisdiction];
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
