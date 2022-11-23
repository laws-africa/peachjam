<template>
  <div
    v-if="provision"
    class="reader-provision-changes-inline ig mb-3"
  >
    <div class="card border-warning">
      <div class="card-header">
        <div class="d-flex">
          <div class="h5 flex-grow-1">
            What changed?
          </div>
          <button
            type="button"
            class="btn btn-secondary"
            @click="close"
          >
            Close
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
                v-for="(diffset, ix) in diffsets"
                :key="ix"
                :value="diffset"
              >
                Between {{ diffset.prev_expression_date }} and {{ diffset.new_expression_date }}
              </option>
            </select>
          </div>

          <div class="col-6">
            <label>
              <input
                v-model="sideBySide"
                type="checkbox"
              > Show changes side-by-side
            </label>
          </div>
        </div>
      </div>

      <div class="card-body reader-provision-changes-inline-body">
        <template v-if="diffsets">
          <diff-content
            v-if="diffset"
            :diffset="diffset"
            :side-by-side="sideBySide"
          />
        </template>
        <template v-else>
          Loading...
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import DiffContent from './DiffContent.vue';

export default {
  name: 'ProvisionDiffContentInline',
  components: { DiffContent },
  props: ['documentId', 'provision'],
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
      const resp = await fetch(`/reader/${this.documentId}/diffsets?id=${this.provision.id}`);
      if (resp.ok) {
        this.diffsets = (await resp.json()).diffsets;
        this.diffset = this.diffsets ? this.diffsets[0] : null;
      }
    },

    close () {
      if (this.originalElement) {
        this.originalElement.style.display = null;
      }
      this.$el.remove();
      this.$destroy();
    }
  }
};
</script>

<style scoped>
.card-header {
  background-color: #ffdf80;
}

.card-body {
  background-color: #fff6da;
}
</style>
