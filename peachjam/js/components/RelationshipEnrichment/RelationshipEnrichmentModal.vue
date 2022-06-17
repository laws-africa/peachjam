<template>
  <div
    class="modal fade"
    tabindex="-1"
    data-bs-keyboard="false"
    data-bs-backdrop="static"
    role="dialog"
    aria-hidden="true"
  >
    <div class="modal-dialog" role="document">
      <div class="modal-content">
        <form @submit.prevent="save" ref="form">
          <div class="modal-header">
            <h5 class="modal-title">
              Add relationship
            </h5>
            <button
              type="button"
              class="btn-close"
              aria-label="Close"
              @click="close"
            />
          </div>

          <div class="modal-body">
            <p>This document...</p>

            <select
              v-model="relationship.predicate_id"
              class="form-control mb-3"
              required
            >
              <option
                v-for="p in predicates"
                :key="p.id"
                :value="p.id"
              >
                {{ p.verb }}
              </option>
            </select>

            <v-select
              v-model="relationship.object_work_id"
              label="title"
              filterable
              placeholder="Choose the related document..."
              :options="objectDocuments"
              :reduce="d => d.expression_frbr_uri"
              @search="onSearch"
            >
              <template slot="no-options">
                Search for a document...
              </template>

              <template #search="{attributes, events}">
                <input
                  class="vs__search"
                  :required="!relationship.object_work_id"
                  v-bind="attributes"
                  v-on="events"
                />
              </template>
            </v-select>
          </div>

          <div class="modal-footer">
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
    }
  },
  emits: ['close', 'save'],
  data: (x) => ({
    predicates: [],
    relationship: x.enrichment,
    objectDocuments: []
  }),

  mounted () {
    document.body.appendChild(this.$el);
    this.predicates = JSON.parse(document.getElementById('predicates').innerText || '[]');
    this.relationship.predicate_id = this.predicates[0].id;
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

    search: debounce(async function (loading, search) {
      const q = encodeURIComponent(search);
      const resp = await fetch('/search/api/documents/?search=' + q + '&page=1&ordering=-score', {
        headers: authHeaders()
      });
      loading(false);
      if (resp.ok) {
        this.objectDocuments = await resp.json();
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
