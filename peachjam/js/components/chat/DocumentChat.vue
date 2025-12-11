<template>
  <div class="document-chat d-flex flex-column h-100">
    <div ref="messageContainer" class="chat-messages flex-grow-1 overflow-auto p-2">
      <div v-if="permissionDeniedHtml">
        <div class="text-center py-5" v-html="permissionDeniedHtml" />
      </div>
      <div v-else-if="threadId === null" class="spinner-when-empty" />
      <template v-else>
        <div v-if="messages.length === 0 && !streaming" class="text-center text-muted py-5">
          {{ $t('Ask a question about this document.') }}
        </div>

        <transition-group name="chat" tag="div">
          <div
            v-for="message in messages"
            :key="message.id"
            class="d-flex mb-2"
            :class="message.role === 'human' ? 'justify-content-end' : 'justify-content-start'"
          >
            <div
              class="chat-bubble text-break"
              :class="message.role === 'human' ? 'chat-bubble-user bg-brand-pale' : 'chat-bubble-agent'"
            >
              <div v-if="message.content_html" v-html="message.content_html" class="chat-content chat-content-html" />
              <div v-else class="chat-content">{{ message.content }}</div>
              <div v-if="message.role === 'ai' && !message.streaming" class="d-flex align-items-center">
                <button class="btn btn-sm btn-outline-secondary border-0" :title="$t('Upvote message')" @click="voteUp(message.id)">
                  <i v-if="votingUp === message.id" class="bi bi-check"/>
                  <i v-else class="bi bi-hand-thumbs-up"/>
                </button>
                <button class="btn btn-sm btn-outline-secondary border-0 ms-1" :title="$t('Downvote message')" @click="voteDown(message.id)">
                  <i v-if="votingDown === message.id" class="bi bi-check"/>
                  <i v-else class="bi bi-hand-thumbs-down"/>
                </button>
                <button class="btn btn-sm btn-outline-secondary border-0 ms-1" :title="$t('Copy to clipboard')" @click="copyToClipboard(message)">
                  <i class="bi bi-copy"/>
                </button>
              </div>
            </div>
          </div>
        </transition-group>

        <div v-if="streaming && awaitingFirstResponse" class="d-flex justify-content-start mb-3">
          <div class="chat-bubble chat-bubble-agent text-muted d-flex align-items-center gap-2">
            <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"/>
            <span>{{ $t('Thinking...') }}</span>
          </div>
        </div>

        <div v-if="error" class="alert alert-warning">{{ error }}</div>
        <div v-if="error && !threadId" class="text-center">
          <button class="btn btn-link" @click="load">{{ $t('Try again') }}</button>
        </div>
      </template>
    </div>

    <form
      v-if="!permissionDeniedHtml"
      class="chat-input p-2"
      @submit.prevent="submit"
      novalidate
    >
      <div class="input-group">
        <input
          ref="messageInput"
          v-model="inputText"
          type="text"
          class="form-control"
          :placeholder="$t('Ask a question')"
          :disabled="streaming"
          @keydown.enter.exact.prevent="submit"
          @keydown.enter.shift.stop
        />
        <button
          class="btn btn-primary"
          :type="streaming ? 'button' : 'submit'"
          :disabled="streaming ? false : !hasInput"
          :title="streaming ? $t('Stop') : $t('Send')"
          @click="streaming ? stopStream() : null"
        >
          <i v-if="!streaming" class="bi bi-send"/>
          <i v-else class="bi bi-stop-circle-fill"/>
        </button>
      </div>
    </form>
  </div>
</template>

<script>
import { csrfToken } from '../../api';
import peachJam from '../../peachjam';
import { marked } from 'marked';

function generateId () {
  if (window.crypto && window.crypto.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default {
  name: 'DocumentChat',
  props: {
    documentId: {
      type: [String, Number],
      required: true
    }
  },
  data () {
    return {
      threadId: null,
      messages: [],
      permissionDeniedHtml: null,
      inputText: '',
      error: null,
      votingUp: null,
      votingDown: null,
      eventSource: null,
      awaitingFirstResponse: false
    };
  },
  computed: {
    hasInput () {
      return this.inputText.trim().length > 0;
    },
    streaming () {
      return Boolean(this.eventSource);
    }
  },
  mounted () {
    this.loadThread();
  },
  methods: {
    /** Load an existing chat thread for this document, if one exists. Sets the threadId if it does, otherwise
     * sets threadId to '' to indicate no existing thread.
     */
    async loadThread () {
      const url = `${peachJam.config.urlLangPrefix}/api/documents/${this.documentId}/chat`;
      try {
        const resp = await fetch(url);
        if (resp.status === 403) {
          await this.handle403(resp);
        } else if (resp.status === 404) {
          // no existing thread
          this.threadId = '';
        } else if (!resp.ok) {
          throw new Error(this.$t('The assistant could not respond right now. Please try again.'));
        } else {
          const data = await resp.json();
          this.threadId = data.thread_id || '';
          this.mergeMessages(data.messages);
        }
        this.focusInputAndScroll();
      } catch (err) {
        console.error(err);
        this.threadId = '';
        this.error = err.message || this.$t('Something went wrong. Please try again.');
      }
    },
    /**
     * Create a new chat thread for this document and set threadId.
     */
    async createThread () {
      const url = `${peachJam.config.urlLangPrefix}/api/documents/${this.documentId}/chat`;
      try {
        const resp = await fetch(url, {
          method: 'POST',
          headers: {
            'X-CSRFToken': await csrfToken()
          }
        });
        if (resp.status === 403) {
          await this.handle403(resp);
        } else if (!resp.ok) {
          throw new Error(this.$t('The assistant could not respond right now. Please try again.'));
        } else {
          const data = await resp.json();
          this.error = null;
          this.permissionDeniedHtml = null;
          this.threadId = data.thread_id;
          this.messages.splice(0, this.messages.length);
          this.mergeMessages(data.messages);
          this.focusInputAndScroll();
        }
      } catch (err) {
        console.error(err);
        this.error = err.message || this.$t('Something went wrong. Please try again.');
      }
    },
    async submit () {
      if (this.streaming || !this.hasInput) {
        return;
      }

      if (!this.threadId) {
        await this.createThread();
        if (!this.threadId) {
          // failed to create thread
          return;
        }
      }

      const userMessage = this.createMessage('human', this.inputText.trim());
      this.messages.push(userMessage);
      this.inputText = '';
      this.error = null;
      this.focusInputAndScroll();
      this.stream(userMessage);
    },
    stream (message) {
      if (this.eventSource) {
        this.eventSource.close();
      }
      this.awaitingFirstResponse = true;
      const url = `${peachJam.config.urlLangPrefix}/api/chats/${this.threadId}/stream?id=${message.id}&c=` + encodeURIComponent(message.content);
      const es = new EventSource(url);
      this.eventSource = es;
      es.addEventListener('chunk', e => {
        const { id, c } = JSON.parse(e.data);
        if (!id) {
          return;
        }
        this.awaitingFirstResponse = false;
        const targetMessage = this.getOrCreateMessage(id, 'ai');
        this.setMessageStreaming(targetMessage, true);
        this.setMessageContent(targetMessage, targetMessage.content + c);
        this.$nextTick(() => {
          this.scrollToBottom();
        });
      });

      es.addEventListener('message', e => {
        // an entire message
        const message = JSON.parse(e.data);
        if (!message || !message.id) {
          return;
        }
        this.awaitingFirstResponse = false;
        const targetMessage = this.getOrCreateMessage(message.id, message.role || 'ai');
        this.setMessageContent(targetMessage, message.content);
        this.setMessageStreaming(targetMessage, false);
        this.$nextTick(() => {
          this.scrollToBottom();
        });
      });

      es.addEventListener('done', () => {
        this.closeStream(es);
        this.finishStreamingUI();
      });

      es.addEventListener('error', err => {
        console.error(err);
        this.error = err.message || this.$t('Something went wrong. Please try again.');
        // remove the message so that the user can try again
        const lastMessage = this.messages[this.messages.length - 1];
        if (!lastMessage || lastMessage.role !== 'ai') {
          this.inputText = message.content;
          this.messages.pop();
        }
        this.closeStream(es);
        this.finishStreamingUI();
      });
    },
    createMessage (role, content) {
      return {
        id: generateId(),
        role,
        content,
        content_html: role === 'ai' && content ? marked.parse(content) : null,
        streaming: false
      };
    },
    getOrCreateMessage (id, role = 'ai') {
      let message = this.messages.find(existingMessage => existingMessage.id === id);
      if (!message) {
        message = {
          id,
          role,
          content: '',
          content_html: null,
          streaming: false
        };
        this.messages.push(message);
      }
      return message;
    },
    setMessageContent (message, content) {
      message.content = content || '';
      if (message.role === 'ai' && message.content.trim().length > 0) {
        message.content_html = marked.parse(message.content);
      } else {
        message.content_html = null;
      }
    },
    mergeMessages (newMessages) {
      for (const msg of newMessages) {
        if (!msg.id) {
          continue;
        }
        const message = this.getOrCreateMessage(msg.id, msg.role || 'ai');
        message.role = msg.role || 'ai';
        this.setMessageContent(message, msg.content || '');
        this.setMessageStreaming(message, false);
      }
    },
    setMessageStreaming (message, streaming) {
      if (message.role !== 'ai') {
        message.streaming = false;
        return;
      }
      message.streaming = Boolean(streaming);
    },
    focusInputAndScroll () {
      this.$nextTick(() => {
        this.scrollToBottom();
        this.focusInput();
      });
    },
    clearStreamingMessages () {
      for (const msg of this.messages) {
        if (msg.streaming) {
          this.setMessageStreaming(msg, false);
        }
      }
    },
    finishStreamingUI () {
      this.focusInputAndScroll();
    },
    closeStream (source) {
      if (source) {
        source.close();
      }
      if (this.eventSource === source) {
        this.eventSource = null;
      }
      this.clearStreamingMessages();
      this.awaitingFirstResponse = false;
    },
    stopStream () {
      if (!this.eventSource) {
        return;
      }
      this.closeStream(this.eventSource);
      this.finishStreamingUI();
    },
    scrollToBottom () {
      const el = this.$refs.messageContainer;
      if (el && typeof el.scrollTo === 'function') {
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
      }
    },
    focusInput () {
      const input = this.$refs.messageInput;
      if (input && typeof input.focus === 'function') {
        input.focus();
      }
    },
    clear () {
      // clear the chat
      this.stopStream();
      this.messages.splice(0, this.messages.length);
      this.error = null;
      this.threadId = '';
    },
    async handle403 (response) {
      try {
        const data = await response.json();
        if (data && data.message_html) {
          this.handlePermissionDenied(data.message_html);
          return;
        }
      } catch (parseErr) {
        console.error(parseErr);
      }
      throw new Error(this.$t("You don't have permission to do that."));
    },
    handlePermissionDenied (messageHtml) {
      this.permissionDeniedHtml = messageHtml;
      this.threadId = null;
      this.messages.splice(0, this.messages.length);
      this.error = null;
      return true;
    },
    async voteUp (messageId) {
      this.votingUp = messageId;
      setTimeout(() => {
        this.votingUp = null;
      }, 1500);
      fetch(`${peachJam.config.urlLangPrefix}/api/chats/${this.threadId}/messages/${messageId}/vote-up`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': await csrfToken()
        }
      });
    },
    async voteDown (messageId) {
      this.votingDown = messageId;
      setTimeout(() => {
        this.votingDown = null;
      }, 1500);
      fetch(`${peachJam.config.urlLangPrefix}/api/chats/${this.threadId}/messages/${messageId}/vote-down`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': await csrfToken()
        }
      });
    },
    async copyToClipboard (message) {
      const textBlob = new Blob([message?.content || ''], { type: 'text/plain' });
      const html = message?.content_html || message?.content || '';
      const htmlBlob = new Blob([html], { type: 'text/html' });

      if (navigator.clipboard?.write && window.ClipboardItem) {
        try {
          // eslint-disable-next-line no-undef
          const item = new ClipboardItem({
            'text/plain': textBlob,
            'text/html': htmlBlob
          });
          await navigator.clipboard.write([item]);
        } catch (err) {
          console.warn('Failed to copy rich content via Clipboard API', err);
        }
      } else if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(html);
        } catch (err) {
          console.warn('Failed to copy HTML as text via Clipboard API', err);
        }
      }
    }
  }
};
</script>

<style scoped>
</style>
