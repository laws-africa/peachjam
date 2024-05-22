<template>
  <div
    v-for="(row, index) in filteredData"
    :key="index"
    :class="`table-row legislation-table__row ${
      row.children.length ? 'has-children' : ''
    }`"
    role="button"
    @click="handleRowClick"
  >
    <div
      v-if="row.children.length"
      class="column-caret indent"
    >
      <i class="bi bi-caret-right-fill" />
      <i class="bi bi-caret-down-fill" />
    </div>
    <div
      v-else
      class="indent"
    />
    <div class="table-row__content-col">
      <div class="content d-flex justify-content-between">
        <div class="content__title">
          <a :href="`${row.work_frbr_uri}`">{{ row.title }}</a>
          <i
            v-if="row.languages.length > 1"
            class="bi bi-translate ps-2"
            :title="$t('Multiple languages available')"
          />
        </div>
        <div v-if="showDates" class="content__secondary">
          {{ row.date }}
        </div>
        <div v-else class="content__secondary">
          {{ row.citation }}
        </div>
        <div
          v-if="row.children.length"
          :id="`row-accordion-${index}`"
          class="accordion-collapse collapse accordion content__children"
          data-bs-parent=".legislation-table__row"
        >
          <div class="accordion-body p-0">
            <div
              v-for="(subleg, subleg_index) in row.children"
              :key="subleg_index"
              class="content mb-3"
            >
              <div class="content__title">
                <a :href="`${subleg.work_frbr_uri}`">{{ subleg.title }}</a>
              </div>
              <div v-if="showDates" class="content__secondary">
                {{ subleg.date }}
              </div>
              <div v-else class="content__secondary">
                {{ subleg.citation }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
export default {
  name: 'LegislationRows',
  props: ['filteredData', 'showDates', 'handleRowClick']
};
</script>
