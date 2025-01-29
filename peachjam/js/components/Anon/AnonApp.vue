<template>
  <header class="bg-light p-2 d-flex">
    <h5 class="mb-0">🥷 {{ title }}</h5>
    <button class="btn btn-success ms-auto" :disabled="saving" @click="save">Save</button>
  </header>
  <div class="main-pane">
    <div class="content-pane">
      <div id="content-root">
        <!-- Note: we have two roots, because targets need a root element with an ID that is inside "content-root" -->
        <div ref="documentRoot" id="document-root" v-html="contentHtml" />
      </div>
    </div>
    <div class="sidebar-pane border-start">
      <ReplacementPane :replacements="replacements" />
    </div>
  </div>
</template>

<script>
import ReplacementPane from './ReplacementPane.vue';
import { unwrap } from './replacements';

export default {
  components: { ReplacementPane },
  props: ['documentId', 'title'],
  data () {
    return {
      replacements: [],
      saving: false,
      contentHtml: document.getElementById('document-content').innerHTML
    };
  },
  methods: {
    async save () {
      const root = this.$refs.documentRoot.cloneNode(true);
      // remove marks
      for (const mark of root.querySelectorAll('mark')) {
        unwrap(mark);
      }

      const html = root.innerHTML;
      const replacements = this.replacements.filter(r => r.applied).map(r => r.serialise());

      this.saving = true;
      try {
        const resp = await fetch(`/admin/anon/${this.documentId}/update`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('input[name=csrfmiddlewaretoken]').value
          },
          body: JSON.stringify({
            content_html: html, replacements
          })
        });
        if (!resp.ok) {
          alert(`Failed to save: ${resp.statusText}`);
        }
      } finally {
        this.saving = false;
      }
    }
  }
};
</script>

<style>
body, html {
  height: 100%;
}

#anon-app {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.main-pane {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
}

.content-pane {
  flex: 2;
  overflow-y: auto;
  padding: 0.5em;
}

.sidebar-pane {
  flex: 1;
  overflow-y: auto;
  padding: 0.5em;
}

#anon-app mark {
  background-color: rgba(255, 165, 0, 0.4);
  padding: 0px;
  color: inherit;
}

#anon-app mark.is-active {
  background-color: rgba(255, 165, 0, 1.0);
}

#anon-app mark.applied {
  background-color: rgba(144, 238, 144, 0.4);
}

#anon-app mark.applied.is-active {
  background-color: rgba(144, 238, 144, 1.0);
}

.list-group-item.replacement.is-active {
  background-color: rgba(255, 165, 0, 0.25);
}

.list-group-item.replacement.applied {
  background-color: rgba(144, 238, 144, 0.4);
}

.list-group-item.replacement.applied.is-active {
  background-color: rgba(144, 238, 144, 0.6);
}

.content-pane mark {
  scroll-margin-top: 5em;
}
</style>
