<template>
  <div>
    <div v-if="this.repo">
      <div v-if="!info">
        Loading...
      </div>
      <div v-else>
        <h3>Download now</h3>
        <div class="mb-3" v-if="info.windows_asset">
          <a :href="info.windows_asset.browser_download_url"
             class="btn btn-lg btn-outline-primary"
          >Pocket Law for Windows ({{ size(info.windows_asset.size) }} MB)</a>
        </div>
        <div class="mb-3" v-if="info.mac_asset">
          <a :href="info.mac_asset.browser_download_url"
             class="btn btn-lg btn-outline-primary"
          >Pocket Law for Mac OS ({{ size(info.mac_asset.size) }} MB)</a>
        </div>
        <dl>
          <dt>Version</dt>
          <dd>{{ info.version }}</dd>
          <dt>Released</dt>
          <dd>{{ info.date }}</dd>
        </dl>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PocketLawDownload',
  props: {
    repo: String,
  },
  data () {
    return {
      info: null
    };
  },
  async mounted () {
    if (this.repo) {
      const url = `https://api.github.com/repos/${this.repo}/releases/latest`;
      let data;
      try {
        const resp = await fetch(url);
        data = await resp.json();
      } catch (e) {
        console.error(e);
        return;
      }
      // get urls
      this.info = {
        version: data.name,
        date: data.created_at.split('T')[0]
      };

      this.info.windows_asset = data.assets.find(asset => asset.name.endsWith('.exe'));
      this.info.mac_asset = data.assets.find(asset => asset.name.endsWith('.dmg'));
    }
  },
  methods: {
    size (bytes) {
      return Math.trunc(bytes / 1024 / 1024);
    }
  }
};
</script>
