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
              v-if="canViewDiffs && diffsets.length"
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

          <div v-if="canViewDiffs" class="col-6 d-none d-lg-block">
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
        <!-- NO PERMISSION -->
        <div v-if="!canViewDiffs">
          <div v-if="permissionDeniedHtml" v-html="permissionDeniedHtml" />
        </div>

        <!-- HAS PERMISSION -->
        <div v-else>
          <template v-if="diffsets.length">
            <diff-content
              v-if="diffset"
              :diffset="diffset"
              :side-by-side="sideBySide"
            />
          </template>
          <template v-else>
            {{ $t('Loading changes') }}
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import DiffContent from './DiffContent.vue';

export default {
  name: 'ProvisionDiffContentInline',
  components: { DiffContent },
  props: {
    documentId: { type: String, required: true },
    provision: { type: Object, required: true },
    frbrExpressionUri: { type: String, required: true },
    serviceUrl: { type: String, required: true }
  },
  data: () => ({
    user: null,
    canViewDiffs: false,
    permissionDeniedHtml: null,
    diffsets: [],
    diffset: null,
    sideBySide: window.matchMedia('(min-width: 992px)').matches,
    originalElement: null,
    wrapperElement: null
  }),

  async mounted () {
    // Setup wrapping logic only if original element exists
    this.originalElement = document.getElementById(this.provision.id);
    if (this.originalElement) {
      this.wrapperElement = document.createElement('div');
      this.wrapperElement.style.position = 'relative';

      // hide original element behind inline diff
      this.originalElement.style.position = 'absolute';
      this.originalElement.style.visibility = 'hidden';
      this.originalElement.style.height = '0';
      this.originalElement.style.top = '0';

      this.originalElement.insertAdjacentElement('beforebegin', this.wrapperElement);
      this.wrapperElement.append(this.originalElement, this.$el);
    }

    await this.loadPermission();
  },

  methods: {
    async loadPermission () {
      if (!this.documentId) return;

      try {
        const resp = await fetch(`/api/documents/${this.documentId}/capabilities?actions=view_provision_diffs`, {
          headers: { 'HX-Current-URL': window.location.href }
        });

        if (!resp.ok) {
          this.canViewDiffs = false;
          return;
        }

        const data = await resp.json().catch(() => null);
        const capability = data?.view_provision_diffs;
        if (capability?.allowed) {
          this.canViewDiffs = true;
          this.permissionDeniedHtml = null;
          await this.loadDiffContentsets();
          return;
        }

        this.canViewDiffs = false;
        this.permissionDeniedHtml = capability?.message_html || null;
      } catch {
        // ignore network errors
      }
    },

    async loadDiffContentsets () {
      const url = `${this.serviceUrl}/e/diffsets${this.frbrExpressionUri}/?id=${this.provision.id}`;
      try {
        const resp = await fetch(url);
        if (resp.ok) {
          const data = await resp.json();
          this.diffsets = data.diffsets || [];
          this.diffset = this.diffsets[0] || null;
        } else {
          console.warn('Failed to load diffsets', resp.status);
        }
      } catch (e) {
        console.error('Error loading diffsets:', e);
      }
    },

    close () {
      if (this.originalElement) {
        this.wrapperElement.insertAdjacentElement('beforebegin', this.originalElement);
        Object.assign(this.originalElement.style, {
          position: null,
          visibility: null,
          height: null,
          top: null
        });
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

.reader-provision-changes-inline select {
  /* ensure the select control is not too wide on small screens */
  max-width: 60vw;
}
</style>
