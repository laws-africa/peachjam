<template>
  <header class="bg-light p-2">
    <div class="d-flex mb-2">
      <h5 class="mb-0">
        🥷
        <a :href="`/admin/peachjam/judgment/${documentId}/change/`">{{ title }}</a>
      </h5>
      <a class="btn btn-link ms-auto" :href="`/admin/peachjam/judgment/${documentId}/change/`">Close</a>
      <button class="btn btn-success ms-2" :disabled="saving" @click="savePublish">Save and publish</button>
      <button class="btn btn-outline-success ms-2" :disabled="saving" @click="saveDraft">Save draft</button>
    </div>
    <input v-model="newCaseName" class="form-control" />
  </header>
  <div class="main-pane">
    <div class="content-pane">
      <div ref="contentRoot" id="content-root">
        <!-- Note: we have two roots, because targets need a root element with an ID that is inside "content-root" -->
        <div ref="documentRoot" id="document-root" v-html="contentHtml" />
      </div>
    </div>
    <div class="sidebar-pane border-start">
      <ul class="nav nav-tabs border-bottom">
        <li class="nav-item">
          <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#replacements-tab" type="button">Replacements</button>
        </li>
        <li class="nav-item">
          <button class="nav-link" data-bs-toggle="tab" data-bs-target="#comments-tab" type="button">Comments</button>
        </li>
      </ul>
      <div class="tab-content">
        <div class="tab-pane fade show active pt-2" id="replacements-tab">
          <ReplacementsPane ref="replacements" :replacements="replacements" :document-id="documentId" />
        </div>
        <div class="tab-pane fade pt-2" id="comments-tab" ref="comments" />
      </div>
    </div>
  </div>
</template>

<script>
import ReplacementsPane from './ReplacementsPane.vue';
import { unwrap } from './replacements';

export default {
  components: { ReplacementsPane },
  props: ['documentId', 'title', 'caseName'],
  data (self) {
    return {
      replacements: [],
      saving: false,
      newCaseName: self.caseName,
      contentHtml: document.getElementById('document-content').innerHTML,
      activityStart: null,
    };
  },
  mounted () {
    const comments = document.getElementById('comments-wrapper');
    if (comments) {
      this.$refs.comments.appendChild(comments);
    }
    this.activityStart = new Date();
  },
  methods: {
    saveDraft () {
      this.save(false);
    },
    savePublish () {
      this.save(true);
    },
    async save (published) {
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
            case_name: this.newCaseName,
            content_html: html,
            anonymised: true,
            published,
            replacements,
            activity_start: this.activityStart.toISOString(),
            activity_end: new Date().toISOString()
          })
        });
        if (resp.ok) {
          this.activityStart = new Date();
        } else {
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
  padding: 0.5em;
  display: flex;
  flex-direction: column;
}

.tab-content {
  flex-grow: 1;
  overflow-y: auto;
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
  background-color: #aeffae;
}

#anon-app mark.applied.is-active {
  background-color: #00ff00;
}

.list-group-item.replacement.is-active {
  background-color: rgba(255, 165, 0, 0.25);
}

.list-group-item.replacement.applied {
  background-color: #aeffae;
}

.list-group-item.replacement.applied.is-active {
  background-color: #00ff00;
}

.content-pane mark {
  scroll-margin-top: 5em;
}
</style>
