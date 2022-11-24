<template>
  <div
    v-if="provision"
    class="reader-provision-changes-inline ig mb-3"
  >
    <div class="card border-warning">
      <div class="card-header">
        <div class="d-flex">
          <div class="h5 flex-grow-1">
            {{ $t('What changed') }}?
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
          <div class="col-6">
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

          <div class="col-6">
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
import { getBaseUrl } from './index';

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
    }
  },
  data: () => ({
    sideBySide: true,
    diffsets: [],
    diffset: null
  }),

  mounted () {
    this.loadDiffContentsets();
    this.originalElement = document.getElementById(this.provision.id);
    if (this.originalElement) {
      this.originalElement.style.display = 'none';
      this.originalElement.insertAdjacentElement('beforebegin', this.$el);
    }
  },

  methods: {
    async loadDiffContentsets () {
      const url = `${getBaseUrl()}/e/diffsets${this.frbrExpressionUri}/?id=${this.provision.id}`;
      const resp = await fetch(url);
      if (resp.ok) {
        this.diffsets = (await resp.json()).diffsets;
        this.diffset = this.diffsets ? this.diffsets[0] : null;
      }
    },

    close () {
      if (this.originalElement) {
        this.originalElement.style.display = null;
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
