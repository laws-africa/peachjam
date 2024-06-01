<template>
  <tr
    :class="`${row.children && row.children.length ? 'has-children' : ''}`"
    role="button"
    @click="handleRowClick"
  >
    <td class="cell-toggle">
      <div
        v-if="row.children && row.children.length"
        class="indent"
        role="button"
        @click="$emit('toggle')"
      >
        <i class="bi bi-caret-right-fill" />
        <i class="bi bi-caret-down-fill" />
      </div>
    </td>
    <td class="cell-title">
      <a :href="`${row.work_frbr_uri}`">{{ row.title }}</a>
      <i
        v-if="row.languages != null && row.languages.length > 1"
        class="bi bi-translate ps-2"
        :title="$t('Multiple languages available')"
      />
      <div v-if="row.labels.length" class="d-flex align-items-center">
        <span
          v-for="(label, index) in row.labels"
          :key="index"
          :class="`badge rounded-pill bg-${label.level}`"
        >
          {{ label.name }}
        </span>
      </div>
    </td>
    <td v-if="!hideCitation" class="cell-citation">
      {{ row.citation }}
    </td>
    <td class="cell-date">
      {{ row.year }}
    </td>
  </tr>
</template>

<script>
export default {
  name: 'TableRow',
  props: ['row', 'hideCitation'],
  emits: ['toggle']
};
</script>
