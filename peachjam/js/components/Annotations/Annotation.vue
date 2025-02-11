<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <div class="card">
      <div class="card-body">
        <div>
          <div class="dropdown text-end">
            <a
              id="dropdownMenuButton"
              class="btn btn-link"
              type="button"
              data-bs-toggle="dropdown"
              aria-haspopup="true"
              aria-expanded="false"
            >
              <i class="bi bi-three-dots" />
            </a>
            <div class="dropdown-menu" aria-labelledby="dropdownMenuButton">
              <a class="dropdown-item" @click="editAnnotation">Edit</a>
              <a class="dropdown-item" @click="deleteAnnotation">Delete</a>
            </div>
          </div>
        </div>
        <p>{{ annotation.annotation.text }}</p>
      </div>
    </div>
  </la-gutter-item>
</template>
<script>
export default {
  name: 'AnnotationItem',
  props: {
    annotation: {
      type: Object,
      default: null
    },
    viewRoot: HTMLElement,
    gutter: HTMLElement,
    useSelectors: Boolean
  },
  data: () => ({
    marks: [],
    anchorElement: null
  }),
  methods: {
    editAnnotation () {
      console.log('edit annotation');
      this.$emit('edit-annotation', this.annotation);
    },
    deleteAnnotation () {
      console.log('delete annotation');
      this.$emit('delete-annotation', this.annotation);
    }
  },

  mounted () {
    console.log('annotation', this.annotation.annotation);
    this.anchorElement = document.getElementById(this.annotation.annotation.target.anchor_id);
    this.gutter.appendChild(this.$el);
  }

};
</script>
