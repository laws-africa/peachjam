<template>
  <dialog
    ref="dialog"
    class="search-box border rounded shadow p-3"
    :style="overlayStyle"
    aria-labelledby="omnibox-heading"
    @cancel.prevent="close"
    @keydown.esc.prevent.stop="close"
    @click="outsideClick"
  >
    <h2 id="omnibox-heading" class="visually-hidden">
      {{ $t('Search and shortcuts') }}
    </h2>
    <form class="d-flex align-items-center gap-2" @submit.prevent="search()">
      <input
        ref="input"
        v-model="query"
        type="search"
        class="form-control"
        :placeholder="placeholder"
        :aria-label="inputLabel"
        autocomplete="off"
        @keydown.down.prevent="focusResult(0)"
        @keydown.up.prevent="focusResult(-1)"
      >
      <button type="submit" class="btn btn-primary" :disabled="!query.trim()">
        {{ $t('Search') }}
      </button>
      <button
        type="button"
        class="btn-close flex-shrink-0"
        :aria-label="$t('Close search')"
        @click="close"
      />
    </form>
    <div class="search-box__results mt-3" @keydown="resultKeydown">
      <p
        class="visually-hidden"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <template v-if="loading">
          {{ $t('Loading shortcuts') }}
        </template>
        <template v-else>
          {{ $t('{count} suggestions available', { count: resultCount }) }}
        </template>
      </p>
      <p v-if="shortcutsError" class="text-body-secondary small">
        {{ $t('Your shortcuts could not be loaded. You can still search.') }}
      </p>
      <section
        v-for="group in groups"
        :key="group.key"
        :aria-labelledby="`omnibox-${group.key}`"
        class="mb-3"
      >
        <h3 :id="`omnibox-${group.key}`" class="h6 text-body-secondary">
          {{ group.label }}
        </h3>
        <ul class="list-group list-group-flush">
          <li v-for="item in group.items" :key="item.id" class="list-group-item px-0 py-0">
            <a
              v-if="item.url"
              :href="item.url"
              class="search-box__result d-flex align-items-center gap-2 py-2"
              @click="$emit('shortcut', $event, item)"
            >
              <i :class="icon(item)" aria-hidden="true" />
              <span class="flex-grow-1">{{ item.text }}</span>
              <span class="badge text-bg-secondary">{{ typeLabel(item) }}</span>
            </a>
            <button
              v-else
              type="button"
              class="search-box__result btn btn-link w-100 d-flex align-items-center gap-2 text-start"
              @click="search(item.text, item.suggestionType)"
            >
              <i class="bi bi-search" aria-hidden="true" />
              <span class="flex-grow-1">{{ item.text }}</span>
              <span class="badge text-bg-secondary">{{ item.meta }}</span>
            </button>
          </li>
        </ul>
      </section>
      <p v-if="!resultCount && !loading && !suggestionsLoading" class="text-body-secondary">
        <template v-if="query.trim()">
          {{ $t('Press Enter to search.') }}
        </template>
        <template v-else-if="userId !== null">
          {{ $t('Start typing to search. Your recent searches and saved items will appear here.') }}
        </template>
        <template v-else>
          {{ $t('Start typing to find documents, courts, judges and places.') }}
        </template>
      </p>
      <p v-if="suggestionsLoading" class="text-body-secondary small" role="status">
        {{ $t('Loading search suggestions') }}
      </p>
      <p v-if="suggestionsError" class="text-body-secondary small" role="status">
        {{ $t('Search suggestions could not be loaded. Press Enter to search.') }}
      </p>
    </div>
  </dialog>
</template>

<script>
export default {
  name: 'SearchBox',
  props: {
    modelValue: { type: String, default: '' },
    groups: { type: Array, default: () => [] },
    userId: { type: Number, default: null },
    loading: Boolean,
    shortcutsError: Boolean,
    suggestionsLoading: Boolean,
    suggestionsError: Boolean
  },
  emits: ['update:modelValue', 'search', 'shortcut', 'close'],
  data () {
    return {
      query: this.modelValue,
      placeholder: '',
      inputLabel: '',
      anchor: null,
      overlayStyle: {},
      restoringFocus: false,
      isOpen: false,
      isMobile: false
    };
  },
  computed: {
    resultCount () {
      return this.groups.reduce((count, group) => count + group.items.length, 0);
    }
  },
  watch: {
    modelValue (value) { this.query = value; },
    query (value) { this.$emit('update:modelValue', value); }
  },
  mounted () {
    window.addEventListener('resize', this.position);
    window.addEventListener('scroll', this.position, true);
    document.addEventListener('pointerdown', this.documentPointerdown);
    document.addEventListener('focusin', this.documentFocusin);
    window.visualViewport?.addEventListener('resize', this.position);
    window.visualViewport?.addEventListener('scroll', this.position);
  },
  beforeUnmount () {
    this.close();
    window.removeEventListener('resize', this.position);
    window.removeEventListener('scroll', this.position, true);
    document.removeEventListener('pointerdown', this.documentPointerdown);
    document.removeEventListener('focusin', this.documentFocusin);
    window.visualViewport?.removeEventListener('resize', this.position);
    window.visualViewport?.removeEventListener('scroll', this.position);
  },
  methods: {
    show (anchor) {
      if (this.restoringFocus || this.isOpen) return false;
      this.anchor = anchor;
      this.placeholder = anchor.placeholder;
      this.inputLabel = anchor.getAttribute('aria-label') || this.$t('Search documents');
      this.query = anchor.value;
      this.isOpen = true;
      this.isMobile = window.innerWidth < 992;
      this.anchorForm = anchor.form || anchor;
      this.previousVisibility = this.anchorForm.style.visibility;
      this.previousOverflow = document.body.style.overflow;
      this.position();
      this.anchorForm.style.visibility = 'hidden';
      if (this.isMobile) {
        document.body.style.overflow = 'hidden';
        this.$refs.dialog.showModal();
      } else {
        this.$refs.dialog.show();
      }
      this.$refs.input.focus({ preventScroll: true });
      return true;
    },
    close (restoreFocus = true) {
      if (!this.isOpen) return;
      this.isOpen = false;
      this.restoringFocus = true;
      if (this.anchor?.isConnected && this.anchor.value !== this.query) {
        this.anchor.value = this.query;
        this.anchor.dispatchEvent(new Event('input', { bubbles: true }));
      }
      this.anchorForm.style.visibility = this.previousVisibility;
      this.$refs.dialog.close();
      if (this.isMobile) document.body.style.overflow = this.previousOverflow;
      if (restoreFocus && this.anchor?.isConnected) this.anchor.focus({ preventScroll: true });
      this.anchor = null;
      this.$emit('close');
      this.$nextTick(() => { this.restoringFocus = false; });
    },
    search (text = this.query, suggestion = null) {
      const query = text.trim();
      if (!query) return;
      this.$emit('search', query, suggestion);
    },
    position () {
      if (!this.anchor) return;
      if (this.isMobile !== (window.innerWidth < 992)) {
        this.close();
        return;
      }
      const viewport = window.visualViewport;
      const height = viewport?.height || window.innerHeight;
      if (window.innerWidth < 992) {
        this.overlayStyle = { top: `${viewport?.offsetTop || 0}px`, left: '0', width: '100%', height: `${height}px` };
      } else {
        const rect = this.anchorForm.getBoundingClientRect();
        const width = Math.min(Math.max(rect.width, 640), window.innerWidth - 32);
        const left = Math.min(Math.max(16, rect.left), window.innerWidth - width - 16);
        const top = Math.max(16, Math.min(rect.top, height / 2));
        this.overlayStyle = { top: `${top}px`, left: `${left}px`, width: `${width}px`, maxHeight: `${height - top - 16}px` };
      }
    },
    outsideClick (event) {
      if (event.target !== this.$refs.dialog) return;
      const rect = this.$refs.dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) this.close();
    },
    documentPointerdown (event) {
      if (this.isOpen && !this.isMobile && !this.$refs.dialog.contains(event.target)) this.close(false);
    },
    documentFocusin (event) {
      if (this.isOpen && !this.isMobile && !this.$refs.dialog.contains(event.target)) this.close(false);
    },
    focusResult (index) {
      const results = this.$refs.dialog.querySelectorAll('.search-box__result');
      const target = results[index < 0 ? results.length - 1 : index];
      if (target) target.focus();
    },
    resultKeydown (event) {
      if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
      const results = Array.from(this.$refs.dialog.querySelectorAll('.search-box__result'));
      const index = results.indexOf(event.target);
      if (index < 0) return;
      event.preventDefault();
      const next = index + (event.key === 'ArrowDown' ? 1 : -1);
      if (next < 0 || next >= results.length) this.$refs.input.focus();
      else results[next].focus();
    },
    icon (item) {
      return { document: 'bi bi-star-fill', folder: 'bi bi-folder', saved_search: 'bi bi-star-fill', history: 'bi bi-clock-history' }[item.type];
    },
    typeLabel (item) {
      return item.meta || { document: this.$t('Saved document'), folder: this.$t('Saved folder'), saved_search: this.$t('Saved search'), history: this.$t('Recent search') }[item.type];
    }
  }
};
</script>

<style scoped>
.search-box {
  position: fixed;
  margin: 0;
  max-width: none;
  max-height: none;
  color: var(--bs-body-color);
  background: var(--bs-body-bg);
  z-index: 1050;
}

.search-box[open] {
  display: flex;
  flex-direction: column;
}

.search-box::backdrop {
  background: rgba(0, 0, 0, 0.25);
}

.search-box__results {
  overflow-y: auto;
  min-height: 0;
  overscroll-behavior: contain;
}

.search-box__result {
  overflow-wrap: anywhere;
}

@media (max-width: 991.98px) {
  .search-box {
    border-radius: 0 !important;
  }
}
</style>
