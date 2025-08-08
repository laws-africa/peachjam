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
        :style="`width: ${status.progress}%;`"
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
      status: {}
    };
  },
  created () {
    this.offlineEnabled = manager.isTaxonomyAvailableOffline(this.taxonomy);
    this.status = manager.getStatus();
  },
  computed: {
    updating () {
      return this.status.progress > 0;
    }
  },
  methods: {
    async enable () {
      await manager.makeTaxonomyAvailableOffline(this.taxonomy);
      this.offlineEnabled = manager.isTaxonomyAvailableOffline(this.taxonomy);
    },
    disable () {
      manager.removeOfflineTaxonomy(this.taxonomy);
    }
  }
};
</script>
