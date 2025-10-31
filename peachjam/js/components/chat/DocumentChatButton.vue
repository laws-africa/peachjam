<template>
  <div class="document-chat-wrapper">
    <div v-if="open" class="document-chat-popup bg-light border rounded shadow d-flex flex-column">
      <div class="d-flex p-2 pb-0">
        <h5>
          <i class="bi-pj pj-ai"></i>
          Ask {{ assistantName }}
        </h5>
        <button class="btn btn-sm btn-outline-secondary border-0 ms-auto" @click="clear" title="Clear chat">
          <i class="bi bi-trash"></i>
        </button>
        <button class="btn btn-sm btn-outline-secondary border-0 ms-1" @click="open = false" title="Close">
          &times;
        </button>
      </div>
      <div class="flex-grow-1 overflow-y-hidden">
        <document-chat :documentId="documentId" ref="chat"></document-chat>
      </div>
    </div>
    <button
      v-else
      class="btn btn-primary"
      @click="open = true"
    >Ask {{ assistantName }}</button>
  </div>
</template>

<script>
import DocumentChat from './DocumentChat.vue';

export default {
  name: 'DocumentChatButton',
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
      open: false
    };
  },
  methods: {
    clear () {
      this.$refs.chat.clear();
    }
  }
};
</script>

<style scoped>
.document-chat-wrapper {
  position: fixed;
  bottom: 50px;
  right: 20px;
  z-index: 999;
}

.document-chat-popup {
  width: 350px;
  height: 450px;
}
</style>
