<template>
  <nav>
    <ul
      v-if="totalPages > 1"
      class="pagination flex-wrap"
    >
      <li
        v-for="num in pages"
        :key="num"
        class="page-item"
        :class="page === num ? 'active' : ''"
      >
        <a
          class="page-link"
          href="#"
          @click.prevent="setPage(num)"
        >{{ num }}</a>
      </li>

      <li
        v-if="tooManyPages"
        class="page-item disabled"
      >
        <a class="page-link">...</a>
      </li>
    </ul>
  </nav>
</template>

<script>
export default {
  name: 'SearchPagination',
  props: {
    search: {
      type: Object,
      required: true
    },
    page: {
      type: Number,
      required: true
    }
  },
  emits: ['changed'],
  data: () => {
    return {
      maxPages: 15,
      pageSize: 10
    };
  },
  computed: {
    totalPages () {
      return Math.ceil(this.search.count / this.pageSize);
    },
    pages () {
      // numbers from 1 .. number of pages
      return [...Array(Math.min(this.totalPages, this.maxPages)).keys()].map(i => i + 1);
    },
    tooManyPages () {
      return this.totalPages > this.maxPages;
    }
  },
  methods: {
    setPage (num) {
      this.$emit('changed', num);
    }
  }
};
</script>
