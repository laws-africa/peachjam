<template>
  <li class="mb-4 hit">
    <h5 class="mb-0">
      {{ item.title }}
    </h5>
    <div>
      {{ item.matter_type }}
    </div>
    <div>
      {{ item.citation }}
    </div>
    <div>
      <span v-if="item.authoring_body"><strong>{{ item.authoring_body }}</strong> - </span>
      <span class="text-muted">{{ item.date }}</span>
    </div>
    <div>
      {{ item.jurisdiction }}
    </div>
  </li>
</template>

<script>
export default {
  name: 'SearchResult',
  props: {
    item: {
      type: Object,
      default () {
        return {};
      }
    }
  }
};
</script>
