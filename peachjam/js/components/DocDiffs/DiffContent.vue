<template>
  <div>
    <la-akoma-ntoso
      v-if="!sideBySide"
      class="diffset pa-3"
      v-html="diffset.html_diff"
    />
    <div
      v-else
      class="d-flex justify-content-between pa-3"
    >
      <la-akoma-ntoso
        class="diffset diffset-left"
        v-html="diffset.html_diff"
      />
      <la-akoma-ntoso
        class="diffset diffset-right"
        v-html="diffset.html_diff"
      />
    </div>
  </div>
</template>

<script>
export default {
  name: 'DiffContent',
  props: {
    diffset: {
      type: Object,
      required: true
    },
    sideBySide: {
      type: Boolean,
      required: true
    }
  }
};
</script>

<style>
.diffset-left {
  width: 48%;
}
.diffset-left .ins,
.diffset-left ins {
  display: none !important;
}

.diffset-right {
  width: 48%;
}
.diffset-right .del,
.diffset-right del {
  display: none !important;
}
</style>
