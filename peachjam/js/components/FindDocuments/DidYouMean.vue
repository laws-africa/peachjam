<template>
  <div
    v-if="suggestion.did_you_mean"
    class="mb-3"
  >
    Did you mean
    <a
      href="#"
      @click.prevent="suggest"
      v-html="suggestion.did_you_mean.html"
    />?
  </div>
</template>

<script>
export default {
  name: 'DidYouMean',
  props: {
    q: {
      type: String,
      default: ''
    }
  },
  emits: ['suggest'],
  data: () => {
    return {
      suggestion: {}
    };
  },
  watch: {
    async q () {
      this.suggestion = {};

      if (this.q !== '') {
        const params = new URLSearchParams();
        params.append('q', this.q);

        const url = '/api/search/suggest/?' + params.toString();
        try {
          const response = await fetch(url);
          if (response.ok) {
            this.suggestion = await response.json();
          }
        } catch {
        }
      }
    }
  },
  methods: {
    suggest () {
      this.$emit('suggest', this.suggestion.did_you_mean.q);
    }
  }
};
</script>
