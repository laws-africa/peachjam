<template>
  <li class="mb-4 hit">
    <a
      class="h5 text-primary"
      target="_blank"
      rel="noreferrer"
      :href="item.expression_frbr_uri"
      v-html="item.highlight.title || item.title"
    ></a>
    <div>
      <span v-if="showJurisdiction || item.locality" class="me-3">
        <span v-if="showJurisdiction" v-html="getFlag(item)" class="me-1" />
        <span v-if="showJurisdiction">
          {{ item.jurisdiction }}
          <span v-if="item.locality">· </span>
        </span>
        <span v-if="item.locality">{{ item.locality }}</span>
      </span>
      <span class="me-3">{{ item.date }}</span>
      <span class="me-3">{{ item.doc_type }}</span>
      <a
        v-if="debug"
        class="me-3"
        href="#"
        @click.prevent="$emit('explain')"
      >{{ item._score }}</a>
      <span
        v-if="item.court"
        class="me-3"
      >{{ item.court }}</span>
      <span
        v-if="item.authors"
        class="me-3"
      >{{ authors(item) }}</span>
    </div>
    <div v-if="item.citation && item.citation !== item.title">
      <i>{{ item.citation }}</i>
    </div>
    <div>
      {{ item.matter_type }}
    </div>
    <div v-if="labels">
      <span v-for="label in labels" :key="label.code" :class="[ `badge rounded-pill bg-${label.level}` ]">{{ label.name }}</span>
    </div>
    <div v-if="item.pages.length" class="ms-3">
      <div
        v-for="(page, index) in item.pages"
        :key="index"
      >
        <span>
          <a :href="`${item.expression_frbr_uri}#page-${page.page_num}`">Page {{ page.page_num }}</a>:
        </span>
        <span v-if="page.highlight['pages.body']" v-html="page.highlight['pages.body'].join(' ... ')" />
      </div>
    </div>
    <div v-if="item.provisions.length">
      <SearchResultProvision
        v-for="provision in item.provisions"
        :key="provision.id"
        :item="provision"
        :parents="provisionParents(provision)"
        :expression-frbr-uri="item.expressionFrbrUri"
      />
    </div>
    <div v-else class="ms-3">
      <span
        class="snippet"
        v-html="highlights(item)"
      />
    </div>
    <div v-if="debug && item.explanation" class="ms-3 mt-2">
      <h5>Explanation</h5>
      <div class="explanation border p-2">
        <json-table :data="item.explanation" />
      </div>
    </div>
  </li>
</template>

<script>
import JsonTable from './JsonTable.vue';
import SearchResultProvision from './SearchResultProvision.vue';

export default {
  name: 'SearchResult',
  components: {
    JsonTable,
    SearchResultProvision
  },
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
    },
    showJurisdiction: {
      type: Boolean,
      default: false
    },
    documentLabels: {
      type: Array,
      default: () => []
    },
    debug: {
      type: Boolean,
      default: false
    }
  },
  computed: {
    labels () {
      // get documentLabels where the code is in item.labels
      return this.documentLabels.filter(label => (this.item.labels || []).includes(label.code));
    }
  },
  methods: {
    highlights (item) {
      if (item.highlight.content) {
        return item.highlight.content.join(' ... ');
      }
    },
    getFlag (item) {
      const code = item.expression_frbr_uri.split('/')[2].split('-')[0];
      if (code === 'aa') {
        return '<img style="width:1.33333em; vertical-align: baseline" alt="African Union Icon"  src="/static/images/au_icon.png" loading="lazy"/>';
      } else {
        return `<span class="fi fi-${code}"></span>`;
      }
    },
    authors (item) {
      if (item.authors) {
        return Array.isArray(item.authors) ? ', '.join(item.authors) : item.authors;
      }
      return '';
    },
    provisionParents (provision) {
      // zip item.parent_titles and item.parent_ids
      return provision.parent_titles.map((title, index) => {
        return {
          title: title,
          id: provision.parent_ids[index]
        };
      });
    }
  }
};
</script>

<style>
.hit mark {
  font-weight: bold;
  padding: 0px;
  color: inherit;
}
.snippet {
  line-height: 1.3;
  word-break: break-word;
}
.hit .explanation {
  max-height: 50vh;
  overflow-y: auto;
}
</style>
