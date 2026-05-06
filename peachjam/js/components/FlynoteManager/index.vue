<template>
  <div class="flynote-manager">
    <section
      class="flynote-manager__pane flynote-manager__pane--list"
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
    await this.loadRoots();

    const selectedId = this.getSelectedIdFromUrl();
    if (selectedId) {
      await this.selectFlynote(selectedId, { updateUrl: false });
    } else {
      this.loadWorkspace(this.searchUrl);
    }
  },
  beforeUnmount () {
    window.removeEventListener('popstate', this.handlePopState);
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
    async selectFlynote (id, options = { updateUrl: true }) {
      if (!id) return;

      await this.revealFlynote(id);
      this.selectedId = id;
      this.loadWorkspace(this.nodeUrl(this.detailUrl, id));
      if (options.updateUrl) {
        const url = new URL(window.location.href);
        url.searchParams.set('flynote', id);
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
        this.selectFlynote(selectedId, { updateUrl: false });
      } else {
        this.selectedId = null;
        this.loadWorkspace(this.searchUrl);
      }
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
