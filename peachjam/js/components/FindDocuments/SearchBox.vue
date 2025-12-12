<template>
  <div
    v-show="isVisible"
    ref="root"
    class="search-box"
    :class="rootClasses"
    :style="overlayStyle"
  >
    <form class="search-box__form" @submit.prevent="triggerSearch">
      <div class="search-box__icon-wrapper">
        <button
          type="button"
          class="search-box__icon-btn d-flex d-md-none align-items-center justify-content-center"
          :aria-label="$t('Cancel search')"
          @click="handleCancel"
        >
          <i class="bi bi-x-lg" aria-hidden="true" />
        </button>
        <span class="search-box__icon d-none d-md-flex align-items-center justify-content-center">
          <i class="bi bi-search" aria-hidden="true" />
        </span>
      </div>
      <input
        ref="inputEl"
        :value="query"
        type="search"
        class="form-control search-box__input"
        :placeholder="placeholder"
        :aria-label="inputLabel"
        autocomplete="off"
        @input="handleInput"
        @keydown.down.prevent="focusFirstDropdownItem"
        @keydown.up.prevent="focusLastDropdownItem"
      >
      <button
        type="submit"
        class="btn btn-primary ms-2 search-box__submit d-none d-md-block"
        :disabled="!query.trim()"
      >
        {{ $t('Search') }}
      </button>
    </form>
    <div v-if="dropdownItems.length" class="search-box__dropdown">
      <ul ref="dropdownList" class="list-unstyled mb-0" role="listbox">
        <li
          v-for="(item, index) in dropdownItems"
          :key="itemKey(item, index)"
          class="d-flex align-items-center search-box__dropdown-item"
          role="option"
          tabindex="0"
          @click="handleSelect(item)"
          @keydown.enter.prevent="handleSelect(item)"
          @keydown.space.prevent="handleSelect(item)"
          @keydown.down.prevent="focusNextItem($event)"
          @keydown.up.prevent="focusPreviousItem($event)"
          @mousedown.prevent
        >
          <span class="search-box__item-icon d-flex align-items-center justify-content-center me-2">
            <i :class="iconClass(item)" aria-hidden="true" />
          </span>
          <div class="flex-grow-1 text-truncate">
            {{ item.text }}
          </div>
          <small v-if="item.meta" class="text-muted ms-2 text-nowrap">
            {{ item.meta }}
          </small>
        </li>
      </ul>
    </div>
  </div>
</template>

<script>
const DESKTOP_BREAKPOINT = 992;

export default {
  name: 'SearchBox',
  props: {
    modelValue: {
      type: String,
      default: ''
    },
    suggestions: {
      type: Array,
      default: () => []
    },
    history: {
      type: Array,
      default: () => []
    },
    placeholder: {
      type: String,
      default: 'Search...'
    },
    inputLabel: {
      type: String,
      default: 'Search documents'
    }
  },
  emits: ['update:modelValue', 'search', 'cancel'],
  data () {
    return {
      query: this.modelValue || '',
      isVisible: true,
      anchorEl: null,
      overlayStyle: {},
      isDesktopViewport: true,
      outsideClickBound: false
    };
  },
  computed: {
    rootClasses () {
      return {
        'search-box--overlay': this.isOverlayActive
      };
    },
    isOverlayActive () {
      return Boolean(this.anchorEl && this.isDesktopViewport);
    },
    dropdownItems () {
      const trimmed = this.query.trim();
      if (!trimmed) {
        return this.history;
      }
      return this.suggestions;
    }
  },
  watch: {
    modelValue (value) {
      if (value !== this.query) {
        this.query = value || '';
      }
    }
  },
  mounted () {
    this.updateViewportFlag();
    window.addEventListener('resize', this.handleResize, { passive: true });
    document.addEventListener('keydown', this.handleEscapeKey);
  },
  beforeUnmount () {
    window.removeEventListener('resize', this.handleResize);
    this.unbindOutsideClick();
    document.removeEventListener('keydown', this.handleEscapeKey);
  },
  methods: {
    show (anchorEl) {
      this.isVisible = true;
      this.anchorEl = anchorEl;
      this.bindOutsideClick();
      this.updateOverlay();
      this.$nextTick(() => {
        this.focusInput();
      });
    },
    hide () {
      this.isVisible = false;
      this.anchorEl = null;
      this.overlayStyle = {};
      this.unbindOutsideClick();
    },
    handleInput (event) {
      this.query = event.target.value;
      this.emitInputChange();
    },
    emitInputChange () {
      this.$emit('update:modelValue', this.query);
    },
    triggerSearch () {
      const value = this.query.trim();
      if (!value) {
        return;
      }
      this.$emit('search', value);
    },
    handleSelect (item) {
      if (!item || !item.text) {
        return;
      }
      this.query = item.text;
      this.emitInputChange();
      this.triggerSearch();
    },
    handleCancel () {
      this.$emit('cancel');
    },
    focusFirstDropdownItem () {
      if (!this.dropdownItems.length) {
        return;
      }
      this.focusDropdownBoundaryItem('start');
    },
    focusLastDropdownItem () {
      if (!this.dropdownItems.length) {
        return;
      }
      this.focusDropdownBoundaryItem('end');
    },
    focusDropdownBoundaryItem (position) {
      const list = this.$refs.dropdownList;
      if (!list) {
        return;
      }
      const items = Array.from(list.querySelectorAll('[role="option"]'));
      if (!items.length) {
        return;
      }
      const target = position === 'end' ? items[items.length - 1] : items[0];
      if (target && typeof target.focus === 'function') {
        target.focus();
      }
    },
    focusNextItem (event) {
      this.focusDropdownItem(event, 1);
    },
    focusPreviousItem (event) {
      this.focusDropdownItem(event, -1);
    },
    focusDropdownItem (event, delta) {
      const currentItem = event.currentTarget;
      if (!currentItem) {
        return;
      }
      const list = currentItem.parentElement;
      if (!list) {
        return;
      }
      const items = Array.from(list.querySelectorAll('[role=\"option\"]'));
      if (!items.length) {
        return;
      }
      const currentIndex = items.indexOf(currentItem);
      if (currentIndex === -1) {
        return;
      }
      if (delta > 0 && currentIndex === items.length - 1) {
        this.focusInputFromDropdown();
        return;
      }
      if (delta < 0 && currentIndex === 0) {
        this.focusInputFromDropdown();
        return;
      }
      const nextIndex = currentIndex + delta;
      const nextItem = items[nextIndex];
      if (nextItem && typeof nextItem.focus === 'function') {
        nextItem.focus();
      }
    },
    focusInputFromDropdown () {
      this.focusInput();
    },
    handleEscapeKey (event) {
      if (!this.isVisible) {
        return;
      }
      if (event.key === 'Escape' || event.key === 'Esc') {
        event.preventDefault();
        this.handleCancel();
      }
    },
    updateOverlay () {
      if (!this.anchorEl || !this.isDesktopViewport) {
        this.overlayStyle = {};
        return;
      }
      const rect = this.anchorEl.getBoundingClientRect();
      const scrollY = window.scrollY ?? window.pageYOffset ?? 0;
      const scrollX = window.scrollX ?? window.pageXOffset ?? 0;
      this.overlayStyle = {
        position: 'absolute',
        top: `${rect.top + scrollY}px`,
        left: `${rect.left + scrollX}px`,
        width: `${rect.width}px`,
        zIndex: 1050
      };
    },
    handleResize () {
      this.updateViewportFlag();
      this.$nextTick(() => {
        this.updateOverlay();
      });
    },
    updateViewportFlag () {
      this.isDesktopViewport = window.innerWidth >= DESKTOP_BREAKPOINT;
    },
    focusInput () {
      const input = this.$refs.inputEl;
      if (input) {
        input.focus();
        if (typeof input.setSelectionRange === 'function') {
          const length = input.value ? input.value.length : 0;
          input.setSelectionRange(length, length);
        }
      }
    },
    bindOutsideClick () {
      if (this.outsideClickBound) {
        return;
      }
      document.addEventListener('mousedown', this.handleOutsideClick);
      document.addEventListener('touchstart', this.handleOutsideClick);
      this.outsideClickBound = true;
    },
    unbindOutsideClick () {
      if (!this.outsideClickBound) {
        return;
      }
      document.removeEventListener('mousedown', this.handleOutsideClick);
      document.removeEventListener('touchstart', this.handleOutsideClick);
      this.outsideClickBound = false;
    },
    handleOutsideClick (event) {
      const root = this.$refs.root;
      if (!root) {
        return;
      }
      if (root.contains(event.target)) {
        return;
      }
      if (this.anchorEl && this.anchorEl.contains(event.target)) {
        return;
      }
      this.$emit('cancel');
    },
    itemKey (item, index) {
      if (!item) {
        return index;
      }
      if (item.id || item.value) {
        return item.id || item.value;
      }
      if (item.text) {
        return `${item.type || 'item'}-${item.text}-${index}`;
      }
      return index;
    },
    iconClass (item) {
      if (item.type === 'history') {
        return 'bi bi-clock-history';
      }
      return 'bi bi-search';
    }
  }
};
</script>

<style scoped>
.search-box {
  background-color: var(--bs-body-bg);
  border-radius: 0.5rem;
  padding: 1rem;
  position: relative;
}

.search-box--overlay {
  padding: 0;
  border-radius: 0.5rem;
  background-color: var(--bs-body-bg);
  border: 1px solid var(--bs-border-color);
  box-shadow: 0 0.5rem 1.5rem rgba(33, 37, 41, 0.2);
}

.search-box--overlay .search-box__form {
  padding: 0.25rem 0.5rem;
}

.search-box--overlay .search-box__dropdown {
  margin-top: 0.25rem;
}

.search-box__form {
  display: flex;
  align-items: center;
}

.search-box__icon-wrapper {
  width: 2rem;
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  align-items: center;
}

.search-box__icon-btn {
  border: none;
  background: transparent;
  width: 100%;
  height: 100%;
  color: inherit;
}

.search-box__icon {
  width: 100%;
}

.search-box__input {
  flex: 1;
  border-radius: 0;
  border: 1px solid var(--bs-border-color);
  border-width: 0px 0px 1px 0px;
  box-shadow: none;
}

.search-box__input:focus {
  border-width: 0px 0px 1px 0px;
  box-shadow: none;
}

.search-box__submit {
  flex-shrink: 0;
}

.search-box__dropdown {
  margin-top: 0.75rem;
  overflow: hidden;
}

.search-box__dropdown-item {
  cursor: pointer;
  padding: 0.25rem 0.5rem;
}

.search-box__dropdown-item:focus {
  outline: none;
  background-color: var(--bg-brand-pale);
}

.search-box__item-icon {
  width: 2rem;
  flex-shrink: 0;
}

@media (max-width: 992px) {
  .search-box {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 100vh;
    padding: 1rem;
    z-index: 1050;
    display: flex;
    flex-direction: column;
  }

  .search-box__form {
    padding-bottom: 0.5rem;
  }

  .search-box__dropdown {
    margin-top: 0;
    flex: 1;
    overflow-y: auto;
    border: none;
    border-radius: 0;
  }

  .search-box__dropdown-item {
    padding-left: 0;
  }
}
</style>
