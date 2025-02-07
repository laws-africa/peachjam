<template>
  <la-gutter-item
    :anchor.prop="anchorElement"
  >
    <div>
      hello annotation
    </div>
  </la-gutter-item>
</template>
<script>
export default {
  name: 'AnnotationsList',
  components: {},
  data: () => ({
    marks: [],
    anchorElement: null
  })

};
</script>
