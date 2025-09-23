<template>
  <div
    class="modal fade"
    tabindex="-1"
    data-bs-keyboard="false"
    data-bs-backdrop="static"
    role="dialog"
    aria-hidden="true"
  >
    <div
      class="modal-dialog modal-lg"
      role="document"
    >
      <div class="modal-content">
        <form
          ref="form"
          @submit.prevent="save"
        >
          <div class="modal-header">
            <h5 class="modal-title">
              Add relationship
            </h5>
            <button
              type="button"
              class="btn-close"
              :aria-label="$t('Close')"
              @click="close"
            />
          </div>

          <div class="modal-body">
            <p v-if="isForwards">
              The selection...
            </p>

            <v-select
              v-if="!isForwards"
              v-model="relationship.subject_work_id"
              class="mb-3"
              label="title"
              placeholder="Choose the subject document..."
              :options="works"
              :reduce="w => w.id"
              @search="onSearch"
            >
              <template #no-options>
                Search for a document...
              </template>

              <template #search="{attributes, events}">
                <input
                  class="vs__search"
                  :required="!relationship.subject_work_id"
                  v-bind="attributes"
                  v-on="events"
                >
              </template>
            </v-select>

            <select
              v-model="relationship.predicate_id"
              class="form-control mb-3"
              :required="!predicates.length"
            >
              <option
                v-if="!predicates.length"
                value=""
              >
                No options available. Add Predicates in admin to have options.
              </option>
              <option
                v-for="p in predicates"
                :key="p.id"
                :value="p.id"
              >
                {{ p.verb }}
              </option>
            </select>

            <v-select
              v-if="isForwards"
              v-model="relationship.object_work_id"
              label="title"
              placeholder="Choose the object document..."
              :options="works"
              :reduce="w => w.id"
              @search="onSearch"
            >
              <template #no-options>
                Search for a document...
              </template>

              <template #search="{attributes, events}">
                <input
                  class="vs__search"
                  :required="!relationship.object_work_id"
                  v-bind="attributes"
                  v-on="events"
                >
              </template>
            </v-select>

            <p v-else>
              ... the selection.
            </p>
          </div>

          <div class="modal-footer">
            <button
              disabled
              class="btn btn-outline-secondary"
              type="button"
              @click="reverse"
            >
              Reverse
            </button>

            <button
              type="button"
              class="btn btn-secondary"
              @click="close"
            >
              Cancel
            </button>

            <button
              type="submit"
              class="btn btn-success"
            >
              Add
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { reverseRelationship } from './enrichment';
// @ts-ignore
import vSelect from 'vue-select';
import 'vue-select/dist/vue-select.css';
import { authHeaders } from '../../api';
import debounce from 'lodash.debounce';

export default {
  name: 'RelationshipEnrichmentModal',
  components: { vSelect },
  props: {
    enrichment: {
      type: Object,
      default: null
    },
    thisWorkFrbrUri: String
  },
  emits: ['close', 'save'],
  data: (x) => ({
    predicates: [],
    relationship: x.enrichment,
    works: []
  }),

  computed: {
    isForwards () {
      return this.relationship.subject_work.frbr_uri === this.thisWorkFrbrUri;
    }
  },

  async mounted () {
    document.body.appendChild(this.$el);
    fetch('/api/predicates/', { headers: await authHeaders() })
      .then(resp => resp.ok ? resp.json() : Promise.reject(resp))
      .then(data => {
        this.predicates = data.results;
        if (!this.relationship.predicate_id && this.predicates.length) {
          this.relationship.predicate_id = this.predicates[0].id;
        }
      })
      .catch(err => {
        console.error('Failed to load predicates', err);
      });
    this.modal = new bootstrap.Modal(this.$el);
    this.$el.addEventListener('hidePrevented.bs.modal', this.close);
    this.modal.show();
  },

  unmounted () {
    this.modal.hide();
  },

  methods: {
    onSearch (search, loading) {
      if (search.length) {
        loading(true);
        this.search(loading, search);
      }
    },

    reverse () {
      // reverse the direction of the relationship
      reverseRelationship(this.relationship);
    },

    search: debounce(async function (loading, search) {
      const resp = await fetch('/api/works/?title__icontains=' + encodeURIComponent(search), {
        headers: authHeaders()
      });
      loading(false);
      if (resp.ok) {
        const data = await resp.json();
        this.works = data.results;
      }
    }, 200),

    save () {
      this.$emit('save', this.enrichment);
    },

    close () {
      this.$emit('close');
    }
  }
};
</script>
