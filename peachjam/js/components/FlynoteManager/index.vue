<template>
  <div class="flynote-manager">
    <section
      ref="treePane"
      class="flynote-manager__pane flynote-manager__pane--list bg-light"
      aria-labelledby="main-page-heading"
    >
      <h1 id="main-page-heading" class="h4 mb-3">
        Flynote manager
      </h1>
      <div class="form-check form-switch mb-3">
        <input
          id="flynote-manager-deprecated-only"
          v-model="deprecatedOnly"
          class="form-check-input"
          type="checkbox"
          @change="reloadTree"
        >
        <label class="form-check-label" for="flynote-manager-deprecated-only">
          Deprecated only
        </label>
      </div>
      <div v-if="loading" class="text-muted">
        Loading flynotes...
      </div>
      <div v-if="error" class="alert alert-danger" role="alert">
        {{ error }}
      </div>
      <ul
        v-if="nodes.length"
        class="flynote-tree"
        role="tree"
        aria-label="Flynote tree"
      >
        <flynote-tree-node
          v-for="node in nodes"
          :key="node.id"
          :node="node"
          :selected-id="selectedId"
          @toggle="toggleNode"
          @select="selectNode"
        />
      </ul>
    </section>
    <section
      class="flynote-manager__pane flynote-manager__pane--workspace"
      aria-label="Flynote manager workspace"
      @click="handleWorkspaceClick"
    >
      <ul class="nav nav-tabs border-bottom bg-light px-3 pt-1" role="tablist">
        <li class="nav-item" role="presentation">
          <button
            class="nav-link"
            :class="{ active: activeWorkspace === 'search' }"
            type="button"
            role="tab"
            aria-controls="flynote-manager-search-pane"
            :aria-selected="activeWorkspace === 'search' ? 'true' : 'false'"
            @click="showSearch"
          >
            Search
          </button>
        </li>
        <li class="nav-item" role="presentation">
          <button
            class="nav-link"
            :class="{ active: activeWorkspace === 'flynote' }"
            type="button"
            role="tab"
            aria-controls="flynote-manager-flynote-pane"
            :aria-selected="activeWorkspace === 'flynote' ? 'true' : 'false'"
            :disabled="!selectedId"
            @click="showFlynote"
          >
            Flynote
          </button>
        </li>
      </ul>
      <div class="tab-content p-3">
        <div
          id="flynote-manager-search-pane"
          ref="searchWorkspace"
          class="tab-pane fade"
          :class="{ 'show active': activeWorkspace === 'search' }"
          role="tabpanel"
          tabindex="0"
        />
        <div
          id="flynote-manager-flynote-pane"
          ref="flynoteWorkspace"
          class="tab-pane fade"
          :class="{ 'show active': activeWorkspace === 'flynote' }"
          role="tabpanel"
          tabindex="0"
        />
      </div>
    </section>
  </div>
</template>

<script>
import htmx from 'htmx.org';
import FlynoteTreeNode from './FlynoteTreeNode.vue';

function decorateNode (node) {
  return {
    ...node,
    children: [],
    childrenLoaded: false,
    expanded: false,
    loading: false,
    error: null
  };
}

export default {
  name: 'FlynoteManager',
  components: { FlynoteTreeNode },
  props: {
    treeUrl: {
      type: String,
      required: true
    },
    childUrl: {
      type: String,
      required: true
    },
    pathUrl: {
      type: String,
      required: true
    },
    searchUrl: {
      type: String,
      required: true
    },
    detailUrl: {
      type: String,
      required: true
    }
  },
  data () {
    return {
      nodes: [],
      selectedId: null,
      activeWorkspace: 'search',
      searchLoaded: false,
      deprecatedOnly: false,
      loading: true,
      error: null
    };
  },
  async mounted () {
    window.addEventListener('popstate', this.handlePopState);
    document.body.addEventListener('flynote-updated', this.handleFlynoteUpdated);
    document.body.addEventListener('flynote-merged', this.handleFlynoteMerged);
    await this.loadRoots();

    const selectedId = this.getSelectedIdFromUrl();
    if (selectedId) {
      await this.selectFlynote(selectedId, {
        updateUrl: false,
        workspaceParams: this.getWorkspaceParamsFromUrl()
      });
    } else {
      this.showSearch({ updateUrl: false });
    }
  },
  beforeUnmount () {
    window.removeEventListener('popstate', this.handlePopState);
    document.body.removeEventListener('flynote-updated', this.handleFlynoteUpdated);
    document.body.removeEventListener('flynote-merged', this.handleFlynoteMerged);
  },
  methods: {
    nodeUrl (template, id) {
      return template.replace('/0/', `/${id}/`);
    },
    treeRequestUrl (url) {
      const requestUrl = new URL(url, window.location.origin);
      requestUrl.searchParams.set('deprecated', this.deprecatedOnly ? 'true' : 'false');
      return requestUrl.toString();
    },
    currentSearchUrl () {
      const form = this.$refs.searchWorkspace?.querySelector('form');
      if (!form) return this.searchUrl;

      const requestUrl = new URL(form.getAttribute('action') || this.searchUrl, window.location.origin);
      requestUrl.search = new URLSearchParams(new FormData(form)).toString();
      return requestUrl.toString();
    },
    getSelectedIdFromUrl () {
      const id = new URLSearchParams(window.location.search).get('flynote');
      if (!id) return null;

      const parsed = parseInt(id, 10);
      return Number.isNaN(parsed) ? null : parsed;
    },
    getWorkspaceParamsFromUrl () {
      const pageParams = new URLSearchParams(window.location.search);
      const workspaceParams = new URLSearchParams();
      for (const key of ['tab', 'selected', 'q']) {
        for (const value of pageParams.getAll(key)) {
          workspaceParams.append(key, value);
        }
      }
      return workspaceParams.toString();
    },
    findNode (id, nodes = this.nodes) {
      for (const node of nodes) {
        if (node.id === id) return node;
        const child = this.findNode(id, node.children);
        if (child) return child;
      }
      return null;
    },
    async loadRoots () {
      this.loading = true;
      this.error = null;
      try {
        const response = await fetch(this.treeRequestUrl(this.treeUrl));
        if (!response.ok) throw new Error(response.statusText);
        const data = await response.json();
        this.nodes = data.results.map(decorateNode);
      } catch {
        this.error = 'Unable to load flynotes.';
      }
      this.loading = false;
    },
    async reloadTree () {
      const searchUrl = this.currentSearchUrl();
      this.nodes = [];
      await this.loadRoots();
      if (this.searchLoaded) {
        this.loadSearchWorkspace(searchUrl);
      }
      if (this.selectedId) {
        await this.revealFlynote(this.selectedId);
        this.scrollSelectedNodeIntoView();
      }
    },
    async loadNodeChildren (node) {
      if (!node.has_children || node.loading || node.childrenLoaded) return;
      node.loading = true;
      node.error = null;
      try {
        const response = await fetch(this.treeRequestUrl(this.nodeUrl(this.childUrl, node.id)));
        if (!response.ok) throw new Error(response.statusText);
        const data = await response.json();
        node.children = data.results.map(decorateNode);
        node.childrenLoaded = true;
      } catch {
        node.error = 'Unable to load child flynotes.';
      }
      node.loading = false;
    },
    async toggleNode (node) {
      if (!node.has_children || node.loading) return;

      if (!node.childrenLoaded) {
        await this.loadNodeChildren(node);
      }
      node.expanded = !node.expanded;
    },
    selectNode (node) {
      this.selectFlynote(node.id);
    },
    showSearch (options = {}) {
      this.activeWorkspace = 'search';
      if (!this.searchLoaded) {
        this.loadSearchWorkspace(this.searchUrl);
      }
      if (options.updateUrl !== false) {
        const url = new URL(window.location.href);
        url.searchParams.delete('flynote');
        url.searchParams.delete('tab');
        url.searchParams.delete('selected');
        url.searchParams.delete('q');
        window.history.pushState({}, '', url);
      }
    },
    showFlynote () {
      if (this.selectedId) {
        this.activeWorkspace = 'flynote';
      }
    },
    async selectFlynote (id, options = {}) {
      if (!id) return;

      await this.revealFlynote(id);
      this.selectedId = id;
      this.activeWorkspace = 'flynote';
      this.scrollSelectedNodeIntoView();
      let detailUrl = this.nodeUrl(this.detailUrl, id);
      if (options.workspaceParams) {
        detailUrl = `${detailUrl}?${options.workspaceParams}`;
      }
      this.loadFlynoteWorkspace(detailUrl);
      if (options.updateUrl !== false) {
        const url = new URL(window.location.href);
        url.searchParams.set('flynote', id);
        url.searchParams.delete('tab');
        url.searchParams.delete('selected');
        url.searchParams.delete('q');
        window.history.pushState({ flynoteId: id }, '', url);
      }
    },
    async revealFlynote (id) {
      const response = await fetch(this.nodeUrl(this.pathUrl, id));
      if (!response.ok) return;
      const data = await response.json();
      for (const pathId of data.path.slice(0, -1)) {
        const node = this.findNode(pathId);
        if (!node) return;
        await this.loadNodeChildren(node);
        node.expanded = true;
      }
    },
    scrollSelectedNodeIntoView () {
      this.$nextTick(() => {
        const treePane = this.$refs.treePane;
        if (!treePane || !this.selectedId) return;

        const selected = treePane.querySelector(`[data-flynote-tree-id="${this.selectedId}"]`);
        selected?.scrollIntoView({ block: 'nearest' });
      });
    },
    loadSearchWorkspace (url) {
      htmx.ajax('GET', this.treeRequestUrl(url), {
        target: this.$refs.searchWorkspace,
        swap: 'innerHTML'
      });
      this.searchLoaded = true;
    },
    loadFlynoteWorkspace (url) {
      htmx.ajax('GET', url, {
        target: this.$refs.flynoteWorkspace,
        swap: 'innerHTML'
      });
    },
    handleWorkspaceClick (event) {
      const link = event.target.closest('a[data-flynote-manager-link]');
      if (!link) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;

      event.preventDefault();
      const id = parseInt(link.dataset.flynoteId, 10);
      if (!Number.isNaN(id)) {
        this.selectFlynote(id);
      }
    },
    handlePopState () {
      const selectedId = this.getSelectedIdFromUrl();
      if (selectedId) {
        this.selectFlynote(selectedId, {
          updateUrl: false,
          workspaceParams: this.getWorkspaceParamsFromUrl()
        });
      } else {
        this.selectedId = null;
        this.showSearch({ updateUrl: false });
      }
    },
    handleFlynoteUpdated (event) {
      const node = this.findNode(event.detail.id);
      if (!node) return;

      node.name = event.detail.name;
      node.deprecated = event.detail.deprecated;
    },
    async handleFlynoteMerged (event) {
      const parentId = event.detail.parentId;
      this.selectedId = event.detail.targetId;
      this.activeWorkspace = 'flynote';

      if (!parentId) {
        await this.loadRoots();
        return;
      }

      const parent = this.findNode(parentId);
      if (!parent) return;

      parent.childrenLoaded = false;
      parent.children = [];
      await this.loadNodeChildren(parent);
      parent.expanded = true;
    }
  }
};
</script>

<style scoped>
.flynote-manager {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
}

.flynote-manager__pane {
  min-height: 0;
  overflow-y: auto;
}

.flynote-manager__pane--list {
  flex: 0 0 22rem;
  border-right: 1px solid var(--bs-border-color);
  padding: 1rem;
}

.flynote-manager__pane--workspace {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  overflow: hidden;
}

.flynote-manager__pane--workspace > .nav {
  flex: 0 0 auto;
}

.flynote-manager__pane--workspace > .tab-content {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.flynote-tree {
  padding-left: 0;
  list-style: none;
}
</style>
