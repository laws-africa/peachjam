<template>
  <li
    class="flynote-tree__item"
    role="treeitem"
    :aria-expanded="node.has_children ? String(node.expanded) : undefined"
  >
    <div
      class="flynote-tree__row"
      :data-flynote-tree-id="node.id"
      :class="{
        'flynote-tree__row--selected': selectedId === node.id,
        'flynote-tree__row--deprecated': node.deprecated
      }"
    >
      <span
        v-if="node.has_children"
        class="flynote-tree__toggle"
        :aria-label="node.expanded ? `Collapse ${node.name}` : `Expand ${node.name}`"
        @click="$emit('toggle', node)"
      >
        <span aria-hidden="true">{{ node.expanded ? '▼' : '▶' }}</span>
      </span>
      <span v-else class="flynote-tree__spacer" aria-hidden="true" />
      <button
        type="button"
        class="btn btn-sm flynote-tree__select"
        :class="selectedId === node.id ? 'btn-primary' : 'btn-link'"
        @click="$emit('select', node)"
      >
        <span class="flynote-tree__name">
          <span>{{ node.name }}</span>
          <span v-if="node.is_new" class="badge text-bg-success ms-2">New</span>
        </span>
        <span class="badge text-bg-light bg-white border ms-2">{{ node.document_count }}</span>
        <span v-if="node.deprecated" class="visually-hidden"> Deprecated </span>
      </button>
    </div>

    <div v-if="node.loading" class="flynote-tree__status text-muted">
      Loading...
    </div>
    <div v-if="node.error" class="flynote-tree__status text-danger">
      {{ node.error }}
    </div>

    <ul
      v-if="node.expanded && node.children.length"
      class="flynote-tree__children"
      role="group"
    >
      <flynote-tree-node
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :selected-id="selectedId"
        @toggle="$emit('toggle', $event)"
        @select="$emit('select', $event)"
      />
    </ul>
  </li>
</template>

<script>
export default {
  name: 'FlynoteTreeNode',
  props: {
    node: {
      type: Object,
      required: true
    },
    selectedId: {
      type: Number,
      default: null
    }
  },
  emits: ['toggle', 'select']
};
</script>

<style scoped>
.flynote-tree__children {
  padding-left: 1.25rem;
  list-style: none;
}

.flynote-tree__row {
  display: flex;
  align-items: center;
  min-width: 0;
}

.flynote-tree__row--deprecated {
  opacity: 0.65;
}

.flynote-tree__toggle,
.flynote-tree__spacer {
  flex: 0 0 1rem;
  width: 1rem;
  text-decoration: none;
  text-align: center;
}

.flynote-tree__select {
  display: flex;
  flex: 1 1 auto;
  justify-content: space-between;
  min-width: 0;
  text-align: start;
  text-decoration: none;
  padding: 0.15rem 0.15rem;
}

.flynote-tree__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flynote-tree__status {
  margin-left: 2rem;
  padding: 0.25rem 0;
  font-size: 0.875rem;
}
</style>
