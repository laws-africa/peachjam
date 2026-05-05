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
  mounted () {
    this.loadRoots();
    this.loadWorkspace(this.searchUrl);
  },
  methods: {
    nodeUrl (template, id) {
      return template.replace('/0/', `/${id}/`);
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
    async toggleNode (node) {
      if (!node.has_children || node.loading) return;

      if (node.childrenLoaded) {
        node.expanded = !node.expanded;
        return;
      }

      node.loading = true;
      node.error = null;
      try {
        const response = await fetch(this.nodeUrl(this.childUrl, node.id));
        if (!response.ok) throw new Error(response.statusText);
        const data = await response.json();
        node.children = data.results.map(decorateNode);
        node.childrenLoaded = true;
        node.expanded = true;
      } catch {
        node.error = 'Unable to load child flynotes.';
      }
      node.loading = false;
    },
    selectNode (node) {
      this.selectedId = node.id;
      this.loadWorkspace(this.nodeUrl(this.detailUrl, node.id));
    },
    loadWorkspace (url) {
      htmx.ajax('GET', url, {
        target: this.$refs.workspace,
        swap: 'innerHTML'
      });
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
