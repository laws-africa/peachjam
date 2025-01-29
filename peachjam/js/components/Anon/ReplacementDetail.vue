<template>
  <li class="list-group-item replacement" @click="clicked" :class="classes">
    <div v-html="replacement.snippet()" class="mb-1" />
    <div class="d-flex">
      <input type="text" v-model="newText" class="form-control me-auto" />
      <button class="btn btn-success ms-2" @click="apply" :disabled="!dirty" title="Apply"><i class="bi bi-check"></i></button>
      <button class="btn btn-warning ms-2" @click="unapply" :disabled="!replacement.applied" title="Undo"><i class="bi bi-arrow-counterclockwise"></i></button>
    </div>
  </li>
</template>

<script>
export default {
  emits: ['applied', 'unapplied', 'activated'],
  props: ['replacement', 'active'],
  data (self) {
    return {
      newText: self.replacement.newText,
    };
  },
  mounted () {
    this.replacement.mark();
  },
  computed: {
    dirty () {
      return !this.replacement.applied || this.newText !== this.replacement.newText;
    },
    classes () {
      const classes = [];
      if (this.replacement.applied) classes.push('applied');
      if (this.active) classes.push('is-active');
      return classes.join(' ');
    }
  },
  watch: {
    'replacement.marks': function () {
      for (const mark of this.replacement.marks) {
        mark.addEventListener('click', () => {
          this.markClicked();
        });
      }
    }
  },
  methods: {
    apply() {
      this.replacement.newText = this.newText;
      this.replacement.apply();
      this.replacement.mark();
      this.$emit('applied', this.replacement);
    },
    unapply() {
      this.replacement.unapply();
      this.replacement.mark();
      this.$emit('unapplied', this.replacement);
    },
    markClicked() {
      this.activateMarks();
      this.$el.scrollIntoView({ behavior: "smooth" });
      this.$emit('activated', this.replacement);
    },
    clicked () {
      this.activateMarks();
      if (this.replacement.marks.length) {
        this.replacement.marks[0].scrollIntoView({behavior: "smooth"});
      }
      this.$emit('activated', this.replacement);
    },
    activateMarks() {
      // a mark was clicked, activate this replacement
      for (const mark of this.getContentRoot().querySelectorAll('mark.is-active')) {
        mark.classList.remove('is-active');
      }
      for (const mark of this.replacement.marks) {
        mark.classList.add('is-active');
      }
    },
    getContentRoot () {
      return document.querySelector('#content-root');
    }
  }
}
</script>
