<template>
  <h3>Documents available offline</h3>
  <ol>
    <li v-for="doc in inventory.documents" :key="doc.url">
      <a :href="doc.url">{{ doc.title }}</a>
    </li>
    <li v-if="inventory.documents.length === 0">
      No documents available offline.
    </li>
  </ol>
  <div class="mt-4">
    <button
      v-if="inventory.documents.length"
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
      inventory: {
        documents: [],
        topics: []
      }
    };
  },
  created () {
    this.inventory = getManager().getInventory();
  },
  methods: {
    clear () {
      if (confirm('Are you sure you want to delete all offline documents?')) {
        getManager().clearOfflineDocs();
        this.inventory = getManager().getInventory();
      }
    }
  }
};
</script>
