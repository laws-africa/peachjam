<template>
  <table class="table table-sm table-light mb-0">
    <tr v-for="(value, key) in data" :key="key">
      <th style="width: 15%" class="align-baseline">{{ key }}</th>
      <td class="align-baseline">
        <ol v-if="Array.isArray(value)">
          <li v-for="(v, i) in value" :key="i" class="border-bottom">
            <details v-if="typeof v === 'object'" open>
              <summary>(details)</summary>
              <JsonTable :data="v" />
            </details>
            <div v-else>{{ v }}</div>
          </li>
        </ol>
        <details v-else-if="typeof value === 'object'" open>
          <summary>(details)</summary>
          <JsonTable :data="value" />
        </details>
        <div v-else>{{ value }}</div>
      </td>
    </tr>
  </table>
</template>

<script>
export default {
  name: 'JsonTable',
  props: {
    data: {
      type: Object
    }
  }
};
</script>

<style scoped>
</style>
