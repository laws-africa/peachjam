<template>
  <div
    ref="result"
    class="card"
  >
    <div class="card-body">
      <h5 class="card-title">
        {{ result.title }}
      </h5>
      <h6 class="card-subtitle mb-2 text-muted">
        Card subtitle
      </h6>
      <p class="card-text">
        {{ result.content }}
      </p>
      <a
        href="#"
        class="card-link"
      >Card link</a>
      <a
        href="#"
        class="card-link"
      >Another link</a>
    </div>
  </div>
</template>

<script>
import Mark from 'mark.js';

export default {
  name: 'ResultCard',
  props: {
    q: {
      type: String,
      default: ''
    },
    result: {
      type: Object,
      default: () => ({
        title: '',
        content: ''
      })
    }
  },
  mounted () {
    const instance = new Mark(this.$refs.result);
    instance.mark(this.q);
  }
};
</script>

<style scoped>

</style>
