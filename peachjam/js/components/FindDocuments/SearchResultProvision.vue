<template>
  <div class="mb-1">
    <div v-if="parents.length">
      <a :href="`${expressionFrbrUri}#${parents[0].id}`">{{ parents[0].title }}</a>
      <div class="ms-3">
        <SearchResultProvision
          :item="item"
          :parents="parents.slice(1)"
          :expression-frbr-uri="expressionFrbrUri"
        />
      </div>
    </div>
    <div v-else>
      <a :href="`${expressionFrbrUri}#${item.id}`">{{ item.title }}</a>
      <div class="ms-3" v-if="item.highlight['provisions.body']" v-html="item.highlight['provisions.body'].join(' ... ')" />
    </div>
  </div>
</template>

<script>
export default {
  name: 'SearchResultProvision',
  props: {
    item: { type: Object, default: () => {} },
    expressionFrbrUri: { type: String, default: '' },
    parents: { type: Array, default: () => [] }
  }
};
</script>
