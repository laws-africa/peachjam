<template>
  <div
    :class="`doc-table-row ${row.children && row.children.length ? 'has-children' : ''}`"
    role="button"
    @click="handleRowClick"
  >
    <div class="doc-table-cell cell-toggle">
      <div
        v-if="row.children && row.children.length"
        class="indent"
        role="button"
        @click="$emit('toggle')"
      >
        <i class="bi bi-caret-right-fill" />
        <i class="bi bi-caret-down-fill" />
      </div>
    </div>
    <div class="doc-table-cell cell-title">
      <a :href="`${row.work_frbr_uri}`">{{ row.title }}</a>
      <i
        v-if="row.languages != null && row.languages.length > 1"
        class="bi bi-translate ps-2"
        :title="$t('Multiple languages available')"
      />
    </div>
    <div v-if="!hideCitation" class="doc-table-cell cell-citation">
      {{ row.citation }}
    </div>
    <div class="doc-table-cell cell-date">
      {{ row.year }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'TableRow',
  props: ['row', 'hideCitation'],
  emits: ['toggle']
};
</script>
