<template>
  <div class="flynote-manager">
    <section
      class="flynote-manager__pane flynote-manager__pane--list bg-light"
      aria-labelledby="main-page-heading"
    >
      <h1 id="main-page-heading" class="h4 mb-3">
        Flynote manager
      </h1>
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
      ref="workspace"
      class="flynote-manager__pane flynote-manager__pane--detail"
      aria-label="Flynote details"
      @click="handleWorkspaceClick"
    />
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
      this.loadWorkspace(this.searchUrl);
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
        const response = await fetch(this.treeUrl);
        if (!response.ok) throw new Error(response.statusText);
        const data = await response.json();
        this.nodes = data.results.map(decorateNode);
      } catch {
        this.error = 'Unable to load flynotes.';
      }
      this.loading = false;
    },
    async loadNodeChildren (node) {
      if (!node.has_children || node.loading || node.childrenLoaded) return;
      node.loading = true;
      node.error = null;
      try {
        const response = await fetch(this.nodeUrl(this.childUrl, node.id));
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
    async selectFlynote (id, options = {}) {
      if (!id) return;

      await this.revealFlynote(id);
      this.selectedId = id;
      let detailUrl = this.nodeUrl(this.detailUrl, id);
      if (options.workspaceParams) {
        detailUrl = `${detailUrl}?${options.workspaceParams}`;
      }
      this.loadWorkspace(detailUrl);
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
    loadWorkspace (url) {
      htmx.ajax('GET', url, {
        target: this.$refs.workspace,
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
        this.loadWorkspace(this.searchUrl);
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
  padding: 1rem;
}

.flynote-manager__pane--list {
  flex: 0 0 22rem;
  border-right: 1px solid var(--bs-border-color);
}

.flynote-manager__pane--detail {
  flex: 1 1 auto;
}

.flynote-tree {
  padding-left: 0;
  list-style: none;
}
</style>
