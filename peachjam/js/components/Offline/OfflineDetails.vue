<template>
  <div class="card mb-5">
    <h5 class="card-header">Collections available offline</h5>
    <ul class="list-group list-group-flush">
      <li v-for="taxonomy in inventory.taxonomies" :key="taxonomy.url" class="list-group-item">
        <a :href="taxonomy.url">{{ taxonomy.name }}</a>
      </li>
      <li v-if="inventory.taxonomies.length === 0" class="list-group-item">
        No collections available offline.
      </li>
    </ul>
  </div>
  <div class="card mb-3">
    <h5 class="card-header">Documents available offline</h5>
    <ul class="list-group list-group-flush">
      <li v-for="doc in inventory.documents" :key="doc.url" class="list-group-item">
        <a :href="doc.url">{{ doc.title }}</a>
      </li>
      <li v-if="inventory.documents.length === 0" class="list-group-item">
        No documents available offline.
      </li>
    </ul>
  </div>
  <div class="mt-5" v-if="updateable && inventory.documents.length">
    <p>Offline content is updated daily if you're online.</p>
    <button
      class="btn btn-primary"
      :disabled="updating"
      @click="update"
    >
      <span v-if="updating">Updating...</span>
      <span v-else>Update offline content</span>
    </button>
  </div>
  <div class="mt-5" v-if="inventory.documents.length">
    <p>Delete all offline content to free up space or if it is not working correctly.</p>
    <button class="btn btn-danger" @click="clear">
      Delete all offline content
    </button>
  </div>
</template>

<script>
import { manager } from './manager';

export default {
  name: 'OfflineDetails',
  props: ['updateable'],
  data: function () {
    return {
      updating: false,
      inventory: {
        documents: [],
        topics: []
      }
    };
  },
  created () {
    this.inventory = manager.getInventory();
  },
  methods: {
    update () {
      this.updating = true;
      manager.checkForUpdates(true).then(() => {
        this.updating = false;
      });
    },
    clear () {
      if (confirm('Are you sure you want to delete all offline documents?')) {
        manager.clearOfflineDocs();
        this.inventory = manager.getInventory();
      }
    }
  }
};
</script>
