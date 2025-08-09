<template>
  <div>
    <div v-if="offlineEnabled">
      <h3>Offline ready!</h3>
      <p>This content is available when you're offline.</p>
      <button
        class="btn btn-outline-danger"
        @click="disable"
      >
        Delete offline content
      </button>
    </div>
    <div v-else>
      <h3>Offline not enabled</h3>
      <p>Make this content available even without an internet connection.</p>
      <button
        class="btn btn-primary"
        :disabled="updating"
        @click="enable"
      >
        <span v-if="updating">Downloading...</span>
        <span v-else>Make available offline</span>
      </button>
    </div>
    <div v-if="updating" class="progress mt-3">
      <div
        class="progress-bar progress-bar-animated progress-bar-striped"
        role="progressbar"
        :style="`width: ${progress}%`"
      />
    </div>
  </div>
</template>

<script>
import { manager } from './manager';

export default {
  name: 'OfflineTaxonomyStatus',
  props: ['taxonomy'],
  data: function () {
    return {
      offlineEnabled: false,
      progress: 0
    };
  },
  computed: {
    updating () {
      return this.progress > 0;
    }
  },
  created () {
    this.offlineEnabled = manager.isTaxonomyAvailableOffline(this.taxonomy);
  },
  methods: {
    async enable () {
      this.progress = 1;
      for await (const x of manager.makeTaxonomyAvailableOfflineDetails(this.taxonomy)) {
        this.progress = x.completed / x.total * 100;
        await new Promise(resolve => setTimeout(resolve, 0));
      }
      this.progress = 0;
      this.offlineEnabled = manager.isTaxonomyAvailableOffline(this.taxonomy);
    },
    disable () {
      manager.removeOfflineTaxonomy(this.taxonomy);
      this.offlineEnabled = manager.isTaxonomyAvailableOffline(this.taxonomy);
    }
  }
};
</script>
