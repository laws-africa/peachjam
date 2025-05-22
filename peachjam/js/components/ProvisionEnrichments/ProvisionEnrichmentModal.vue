<template>
  <div
    :id="'provision-modal-' + enrichment.id"
    class="modal fade"
    tabindex="-1"
    aria-labelledby="provisionModalLabel"
    aria-hidden="true"
  >
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h1 id="provisionModalLabel" class="modal-title fs-5">
            {{ $t( 'Unconstitutional provision' ) }}
          </h1>
          <button
            type="button"
            class="btn-close"
            data-bs-dismiss="modal"
            aria-label="Close"
          />
        </div>

        <div class="modal-body">
          <div>
            <p class="mb-2">
              <a :href="'#' + enrichment.provision_eid" class="provision-link fw-bold">
                #{{ enrichment.provision_eid }}
              </a>
            </p>

            <div class="px-2">
              <p class="my-2">
                <span v-if="enrichment.resolved" class="badge bg-success">Resolved</span>
              </p>

              <la-akoma-ntoso
                v-if="enrichment.provision_by_eid"
                class="bg-light flash-target content content__akn border-start p-2 border-2 border-danger rounded"
                lang="en"
              >
                <la-decorate-terms popup-definitions link-terms />
                <la-decorate-internal-refs flag popups />
                <div v-html="enrichment.provision_by_eid"></div>
              </la-akoma-ntoso>
            </div>

            <p class="my-2">{{ enrichment.text }}</p>

            <template v-if="enrichment.enrichment_type === 'unconstitutional_provision'">
              <div v-if="enrichment.judgment" class="mb-2 row d-flex align-items-center">
                <div class="col-4">
                  <strong>Judgment:</strong>
                </div>
                <div class="col">
                  <span>
                    <a :href="enrichment.judgment.documents.latest_expression.first.get_absolute_url">
                      {{ enrichment.judgment.documents.latest_expression.first.title }}
                    </a>
                  </span>
                </div>
              </div>

              <div
                v-if="enrichment.date_deemed_unconstitutional"
                class="mb-2 row d-flex align-items-center"
              >
                <div class="col-4">
                  <strong>Date deemed unconstitutional:</strong>
                </div>
                <div class="col">
                  <span>{{ enrichment.date_deemed_unconstitutional }}</span>
                </div>
              </div>

              <div
                v-if="enrichment.end_of_suspension_period"
                class="mb-2 row d-flex align-items-center"
              >
                <div class="col-4">
                  <strong>End of suspension period:</strong>
                </div>
                <div class="col">
                  <span>{{ enrichment.end_of_suspension_period }}</span>
                </div>
              </div>

              <div v-if="enrichment.date_resolved" class="mb-2 row d-flex align-items-center">
                <div class="col-4">
                  <strong>Date resolved:</strong>
                </div>
                <div class="col">
                  <span>{{ enrichment.date_resolved }}</span>
                </div>
              </div>

              <div
                v-if="enrichment.resolving_amendment_work"
                class="mb-2 row d-flex align-items-center"
              >
                <div class="col-4">
                  <strong>Resolving amendment:</strong>
                </div>
                <div class="col">
                  <span>
                    <a :href="enrichment.resolving_amendment_work.frbr_uri">
                      {{ enrichment.resolving_amendment_work.title }}
                    </a>
                  </span>
                </div>
              </div>
            </template>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ProvisionEnrichmentModal',
  props: {
    enrichment: {
      type: Object,
      required: true
    }
  }
};
</script>
