<template>
  <div class="d-flex">
    <div class="dropdown ml-3">
      <button
        class="btn btn-sm dropdown-toggle"
        :class="btnClass"
        type="button"
        data-toggle="dropdown"
        aria-haspopup="true"
        aria-expanded="false"
      >
        {{ $t('Compare to') }}
        <span v-if="compareTo">{{ compareTo.date }}</span>
      </button>
      <div
        class="dropdown-menu"
        aria-labelledby="dropdownMenuButton"
      >
        <a
          v-for="doc in documents"
          :key="doc.id"
          class="dropdown-item"
          :class="itemClass(doc)"
          href="#"
          @click.prevent="toggle(doc)"
        >
          {{ doc.date }}
        </a>
      </div>
    </div>
    <div
      v-if="loading"
      class="ml-3"
    >
      {{ $t('Loading') }}...
    </div>
    <div
      v-if="compareTo"
      class="ml-2"
    >
      <label>
        <input
          v-model="sideBySide"
          type="checkbox"
        > {{ $t('Show changes side-by-side') }}
      </label>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DocumentDiffDropdown',
  props: {
    documents: {
      type: Array,
      required: true
    },
    aknRoot: {
      type: HTMLElement,
      required: true
    },
    documentId: {
      type: String,
      required: true
    }
  },

  data: () => ({
    compareTo: null,
    loading: false,
    sideBySide: true
  }),

  computed: {
    btnClass () {
      return this.compareTo === null ? 'btn-outline-secondary' : 'btn-primary';
    }
  },

  watch: {
    compareTo () {
      this.displayDiff();
    },

    sideBySide () {
      this.displayDiff();
    }
  },

  mounted () {
    this.cleanAknHtml = this.aknRoot.innerHTML;
  },

  methods: {
    toggle (doc) {
      if (this.compareTo === doc) {
        this.compareTo = null;
      } else {
        this.compareTo = doc;
      }
    },

    itemClass (doc) {
      return doc === this.compareTo ? 'active' : '';
    },

    async displayDiff () {
      if (this.compareTo) {
        this.loading = true;
        const resp = await fetch(`/reader/${this.documentId}/document-diff?other=${this.compareTo.id}`);
        this.loading = false;
        if (resp.ok) {
          const diff = (await resp.json()).diff_html;
          let html = '';
          if (this.sideBySide) {
            html = '<div class="d-flex justify-content-between pa-3">' +
                  '<div class="diffset diffset-left">' + diff + '</div>' +
                  '<div class="diffset diffset-right">' + diff + '</div>' +
                  '</div>';
          } else {
            html = '<div class="diffset">' + diff + '</div>';
          }
          // eslint-disable-next-line vue/no-mutating-props
          this.aknRoot.innerHTML = html;
        }
      } else {
        // eslint-disable-next-line vue/no-mutating-props
        this.aknRoot.innerHTML = this.cleanAknHtml;
      }
    }
  }
};
</script>
