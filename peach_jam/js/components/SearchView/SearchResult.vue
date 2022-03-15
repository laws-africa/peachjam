<template>
  <li class="mb-4 hit">
    <h6 class="mb-0"><a :href="`/gazettes/${item.key}`">{{ item.name }}</a></h6>
    <ul class="list-unstyled">
      <li v-for="page in item.pages" :key="page.page_num">
        <span class="text-muted">
          <a :href="`https://gazettes.africa${path}#page=${page.page_num}`">Page {{ page.page_num }}</a>:
        </span>
        <span class="snippet" v-html="highlights(page)"></span>
      </li>
    </ul>
  </li>
</template>

<script>
export default {
  name: 'SearchResult',
  props: ['item'],
  methods: {
    highlights (page) {
      return page.highlight['pages.body'].join(' ... ');
    }
  },
  computed: {
    path () {
      const year = this.item.date.split('-')[0];
      return `/archive/${this.item.jurisdiction}/${year}/${this.item.key}.pdf`;
    }
  }
};
</script>

<style>
.hit mark {
  font-weight: bold;
  padding: 0px;
}

.snippet {
  line-height: 1.3;
  word-break: break-word;
}
</style>
