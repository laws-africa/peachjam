<template>
  <div
    v-if="provision"
    class="reader-provision-changes-inline ig mb-3"
  >
    <div class="card border-warning">
      <div class="card-header">
        <div class="d-flex mb-2 mb-lg-0">
          <div class="h5 flex-grow-1">
            {{ $t('What changed?') }}
          </div>
          <button
            type="button"
            class="btn btn-secondary"
            @click="close"
          >
            {{ $t('Close') }}
          </button>
        </div>

        <div class="row">
          <div class="col-12 col-lg-6">
            <select
              v-if="diffsets"
              v-model="diffset"
              class="form-control"
            >
              <option
                v-for="(item, ix) in diffsets"
                :key="ix"
                :value="item"
              >
                {{ $t('Between {prev_expression_date} and {new_expression_date}', {
                  prev_expression_date: item.prev_expression_date,
                  new_expression_date: item.new_expression_date
                }) }}
              </option>
            </select>
          </div>

          <div class="col-6 d-none d-lg-block">
            <label>
              <input
                v-model="sideBySide"
                type="checkbox"
              >
              {{ $t('Show changes side-by-side') }}
            </label>
          </div>
        </div>
      </div>

      <div class="card-body reader-provision-changes-inline-body">
        <template v-if="diffsets.length">
          <diff-content
            v-if="diffset"
            :diffset="diffset"
            :side-by-side="sideBySide"
          />
        </template>
        <template v-else>
          {{ $t('Loading') }}...
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import DiffContent from './DiffContent.vue';
import debounce from 'lodash/debounce';

export default {
  name: 'ProvisionDiffContentInline',
  components: { DiffContent },
  props: {
    documentId: {
      type: String,
      required: true
    },
    provision: {
      type: Object,
      required: true
    },
    frbrExpressionUri: {
      type: String,
      required: true
    },
    serviceUrl: {
      type: String,
      required: true
    }
  },
  data: () => ({
    originalElement: null,
    wrapperElement: null,
    sideBySide: true,
    diffsets: [],
    diffset: null,
    vw: Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0)
  }),

  watch: {
    vw: {
      immediate: true,
      handler (newVw) {
        // Turn off side by side in mobile view
        if (newVw < 992) {
          this.sideBySide = false;
        }
      }
    }
  },

  mounted () {
    this.loadDiffContentsets();
    this.originalElement = document.getElementById(this.provision.id);
    this.wrapperElement = document.createElement('div');
    this.wrapperElement.style.position = 'relative';
    if (this.originalElement) {
      /**
       * the originalElement's gutter item isn't able to properly anchor to originalElement if it has a style: display:none.
       * So we hide originalElement behind ProvisionDiffInline via absolute positioning, so originalElement's gutter
       * item can anchor correctly.
       * */
      this.originalElement.style.position = 'absolute';
      this.originalElement.style.visibility = 'hidden';
      this.originalElement.style.height = '0';
      this.originalElement.style.top = '0';
      this.originalElement.insertAdjacentElement('beforebegin', this.wrapperElement);
      this.wrapperElement.append(this.originalElement, this.$el);
    }
    window.addEventListener('resize', this.setVw);
  },

  unmounted () {
    window.removeEventListener('resize', this.setVw);
  },

  methods: {
    setVw: debounce(function () {
      this.vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    }, 200),

    async loadDiffContentsets () {
      const url = `${this.serviceUrl}/e/diffsets${this.frbrExpressionUri}/?id=${this.provision.id}`;
      const resp = await fetch(url);
      if (resp.ok) {
        this.diffsets = (await resp.json()).diffsets;
        this.diffset = this.diffsets ? this.diffsets[0] : null;
      }
    },

    close () {
      if (this.originalElement) {
        // Place originalElement back to where it was and remove wrapperElement
        this.wrapperElement.insertAdjacentElement('beforebegin', this.originalElement);
        this.originalElement.style.position = null;
        this.originalElement.style.visibility = null;
        this.originalElement.style.height = null;
        this.originalElement.style.top = null;

        this.wrapperElement.remove();
      }
      this.$el.dispatchEvent(new CustomEvent('close'));
      this.$el.remove();
    }
  }
};
</script>

<style scoped>
.card-header {
  background-color: #ffdf80;
  font-family: var(--bs-body-font-family);
}

.card-body {
  background-color: #fff6da;
}
</style>
