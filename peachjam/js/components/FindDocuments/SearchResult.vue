<template>
  <li :class="`mb-4 hit ${item.best_match ? 'best-match' : ''}`">
    <div class="card" :data-best-match="$t('Best match')">
      <div class="card-body">
        <h5 class="card-title">
          <a
            class="h5 text-primary"
            target="_blank"
            :href="item.expression_frbr_uri"
            @click="$emit('item-clicked')"
            v-html="item.highlight.title || item.title"
          />
        </h5>
        <div class="mb-1">
          <div v-if="item.citation && item.citation !== item.title">
            <i>{{ item.citation }}</i>
          </div>
          <div v-if="item.alternative_names.length">
            <i>
              <span v-for="(name, i) in item.highlight.alternative_names || item.alternative_names" :key="i">
                <span v-if="i > 0">; </span>
                <span v-html="name" />
              </span>
            </i>
          </div>
          <div>
            <span v-if="showJurisdiction || item.locality" class="me-3">
              <span v-if="showJurisdiction" v-html="getFlag(item)" class="me-1" />
              <span v-if="showJurisdiction">
                {{ item.jurisdiction }}
                <span v-if="item.locality">· </span>
              </span>
              <span v-if="item.locality">{{ item.locality }}</span>
            </span>
            <span class="me-3">{{ item.nature }}</span>
            <span class="me-3">{{ item.date }}</span>
            <span
              v-if="item.court"
              class="me-3"
            >{{ item.court }}</span>
            <span
              v-if="item.authors"
              class="me-3"
            >{{ authors(item) }}</span>
            <span v-for="label in labels" :key="label.code" :class="`me-3 badge rounded-pill bg-${label.level}`">{{ label.name }}</span>
            <a
              v-if="debug"
              class="me-3"
              href="#"
              @click.prevent="$emit('explain')"
            >{{ item._score }}</a>
          </div>
          <div>
            {{ item.matter_type }}
          </div>
        </div>
        <div v-if="item.pages.length">
          <div
            v-for="page in item.pages"
            :key="page.page_num"
            class="mb-1"
          >
            <a
              :href="`${item.expression_frbr_uri}#page-${page.page_num}`"
              target="_blank"
              @click="$emit('item-clicked', `page-${page.page_num}`)"
            >{{ $t('Page') }} {{ page.page_num }}</a>:
            <span v-if="page.highlight['pages.body']" v-html="page.highlight['pages.body'].join(' ... ')" />
          </div>
        </div>
        <div v-if="item.provisions.length">
          <SearchResultProvision
            v-for="provision in item.provisions"
            :key="provision.id"
            :item="provision"
            :parents="provisionParents(provision)"
            :expression-frbr-uri="item.expression_frbr_uri"
            @item-clicked="(x) => $emit('item-clicked', x)"
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
  emits: ['explain', 'item-clicked'],
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

.hit.best-match .card {
  box-shadow: 0px 0px 5px 2px gold;
}

.hit.best-match .card::before {
  content: attr(data-best-match);
  position: absolute;
  background: gold;
  padding: 0.25rem 0.25rem;
  right: -1px;
  top: -1px;
  font-size: smaller;
  border-top-right-radius: 6px;
}
</style>
