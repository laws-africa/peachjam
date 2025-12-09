<template>
  <div>
    <div v-if="open" :class="`document-chat-popup bg-white border rounded shadow d-flex flex-column ${expanded ? 'expanded' : ''}`">
      <div class="d-flex bg-light border-bottom">
        <h5 class="p-2 pb-0">
          <i class="bi-pj pj-ai"/>
          {{ $t('Ask {assistantName}', { assistantName }) }}
        </h5>
        <button
          class="btn btn-sm btn-outline-secondary border-0 ms-auto"
          :title="$t('Clear chat')"
          @click="clear"
        >
          <i class="bi bi-trash"/>
        </button>
        <button
          v-if="!expanded"
          class="btn btn-outline-secondary border-0 ms-1 d-none d-lg-inline"
          :title="$t('Expand')"
          @click="expanded = true"
        >
          <i class="bi bi-arrows-angle-expand" />
        </button>
        <button
          v-if="expanded"
          class="btn btn-outline-secondary border-0 ms-1 d-none d-lg-inline"
          :title="$t('Collapse')"
          @click="expanded = false"
        >
          <i class="bi bi-arrows-angle-contract"/>
        </button>
        <button
          class="btn btn-outline-secondary border-0 ms-1"
          data-track-event="Document Chat | Close"
          :title="$t('Close')"
          @click="open = false"
        >&times;</button>
      </div>
      <div class="flex-grow-1 overflow-y-hidden">
        <document-chat ref="chat" :document-id="documentId" />
      </div>
    </div>
    <button
      v-else
      class="btn btn-primary btn-shrink-sm document-chat-button"
      data-track-event="Document Chat | Open"
      @click="open = true"
    >
      <i class="bi-pj pj-ai" />
      {{ $t('Ask {assistantName}', { assistantName }) }}
    </button>
  </div>
</template>

<script>
import DocumentChat from './DocumentChat.vue';

export default {
  name: 'DocumentChatPopup',
  components: {
    DocumentChat
  },
  props: {
    documentId: {
      type: [String, Number],
      required: true
    },
    assistantName: {
      type: [String],
      required: true
    }
  },
  data () {
    return {
      open: false,
      expanded: false
    };
  },
  methods: {
    clear () {
      this.$refs.chat.clear();
    },
    show () {
      this.open = true;
    }
  }
};
</script>

<style scoped>
</style>
