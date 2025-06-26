<template>
  <h3>Documents available offline</h3>
  <ol>
    <li v-for="doc in offlineDocs" :key="doc.url">
      <a :href="doc.url">{{ doc.title }}</a>
    </li>
    <li v-if="offlineDocs.length === 0">
      No documents available offline.

    </li>
  </ol>
  <div class="mt-4">
    <button
      v-if="offlineDocs.length"
      class="btn btn-danger"
      @click="clear"
    >
      Delete all offline documents
    </button>
  </div>
</template>

<script>
import { getManager } from './manager';

export default {
  name: 'OfflineDetails',
  data: function () {
    return {
      offlineDocs: []
    };
  },
  created () {
    this.offlineDocs = getManager().getOfflineDocs();
  },
  methods: {
    clear () {
      if (confirm('Are you sure you want to delete all offline documents?')) {
        getManager().clearOfflineDocs();
        this.offlineDocs = [];
      }
    }
  }
};
</script>
