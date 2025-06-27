<template>
  <h3>Collections available offline</h3>
  <ol class="mb-4">
    <li v-for="taxonomy in inventory.taxonomies" :key="taxonomy.url">
      <a :href="taxonomy.url">{{ taxonomy.name }}</a>
    </li>
    <li v-if="inventory.taxonomies.length === 0">
      No collections available offline.
    </li>
  </ol>
  <h3>Documents available offline</h3>
  <ol class="mb-4">
    <li v-for="doc in inventory.documents" :key="doc.url">
      <a :href="doc.url">{{ doc.title }}</a>
    </li>
    <li v-if="inventory.documents.length === 0">
      No documents available offline.
    </li>
  </ol>
  <button
    v-if="inventory.documents.length"
    class="btn btn-danger"
    @click="clear"
  >
    Delete all offline content
  </button>
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
