<template>
  <div class="document-chat d-flex flex-column h-100 bg-white">
    <header class="chat-header d-flex align-items-center px-3 py-2 border-bottom">
      <div class="chat-header__icon rounded-circle d-flex align-items-center justify-content-center me-2">
        <i class="bi bi-chat-dots"></i>
      </div>
      <div>
        <div class="fw-semibold">Ask this document</div>
        <small class="text-muted">Powered by PeachJam AI assistant</small>
      </div>
    </header>

    <div ref="messageContainer" class="chat-messages flex-grow-1 overflow-auto px-3 py-3">
      <div v-if="messages.length === 0 && !loading" class="text-center text-muted py-5">
        Start the conversation by asking a question about this document.
      </div>

      <transition-group name="chat" tag="div">
        <div
          v-for="message in messages"
          :key="message.id"
          class="d-flex mb-3"
          :class="message.role === 'user' ? 'justify-content-end' : 'justify-content-start'"
        >
          <div
            class="chat-bubble text-break"
            :class="message.role === 'user' ? 'chat-bubble-user bg-primary text-white' : 'chat-bubble-agent bg-light'"
          >
            <div class="chat-content">{{ message.content }}</div>
          </div>
        </div>
      </transition-group>

      <div v-if="loading" class="d-flex justify-content-start mb-3">
        <div class="chat-bubble chat-bubble-agent bg-light text-muted d-flex align-items-center gap-2">
          <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
          <span>Thinking…</span>
        </div>
      </div>

      <div v-if="error" class="alert alert-warning">{{ error }}</div>
    </div>

    <form class="chat-input border-top" @submit.prevent="submit" novalidate>
      <div class="input-group p-2">
        <textarea
          ref="messageInput"
          v-model="inputText"
          class="form-control"
          placeholder="Ask a question…"
          rows="1"
          :disabled="loading"
          @keydown.enter.exact.prevent="submit"
          @keydown.enter.shift.stop
        ></textarea>
        <button class="btn btn-primary" type="submit" :disabled="loading || !isReady">
          <span v-if="!loading">Send</span>
          <span v-else class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
        </button>
      </div>
    </form>
  </div>
</template>

<script>
import { csrfToken } from '../api';

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
      messages: [],
      inputText: '',
      loading: false,
      error: null
    };
  },
  computed: {
    endpoint () {
      return `/api/documents/${this.documentId}/chat`;
    },
    isReady () {
      return this.inputText.trim().length > 0;
    }
  },
  mounted () {
    this.focusInput();
  },
  methods: {
    async submit () {
      if (this.loading || !this.isReady) {
        return;
      }

      const text = this.inputText.trim();
      if (!text) {
        return;
      }

      const userMessage = this.createMessage('user', text);
      this.messages.push(userMessage);
      this.inputText = '';
      this.loading = true;
      this.error = null;

      this.$nextTick(() => {
        this.focusInput();
        this.scrollToBottom();
      });

      try {
        // TODO: server has full context, just send the latest message the user entered
        const payload = {
          messages: this.messages.map(({ role, content }) => ({ role, content }))
        };

        const resp = await fetch(this.endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': await csrfToken()
          },
          body: JSON.stringify(payload)
        });

        if (!resp.ok) {
          throw new Error('The assistant could not respond right now. Please try again.');
        }

        const data = await resp.json();
        const assistantMessages = this.normaliseEvents(data.messages);
        this.mergeMessages(assistantMessages);
      } catch (err) {
        console.error(err);
        this.error = err.message || 'Something went wrong. Please try again.';
      } finally {
        this.loading = false;
        this.$nextTick(() => {
          this.scrollToBottom();
          this.focusInput();
        });
      }
    },
    createMessage (role, content) {
      return {
        id: generateId(),
        role,
        content
      };
    },
    mergeMessages (newMessages) {
      for (const msg of newMessages) {
        const existing = this.messages.find((existingMessage) => existingMessage.id === msg.id);
        if (existing) {
          existing.content = msg.content;
        } else if (msg.content.trim().length > 0) {
          this.messages.push({ ...msg });
        }
      }
    },
    normaliseEvents (events) {
      if (!Array.isArray(events)) {
        return [];
      }

      return events
        .map((event) => {
          const role = this.resolveRole(event);
          const id = event.id || `${role || 'assistant'}-${generateId()}`;
          const content = this.resolveContent(event);
          return {
            id,
            role: role || 'assistant',
            content
          };
        })
        .filter((event) => event.role !== 'system' && event.role !== 'user' && event.content.trim().length > 0);
    },
    resolveRole (event) {
      if (!event) {
        return null;
      }
      if (event.role) {
        return event.role;
      }
      if (event.data && event.data.role) {
        return event.data.role;
      }
      if (event.message && event.message.role) {
        return event.message.role;
      }
      return null;
    },
    resolveContent (event) {
      const mapContentArray = (items) => {
        return items
          .map((item) => {
            if (!item) {
              return '';
            }
            if (typeof item === 'string') {
              return item;
            }
            if (item.text) {
              return item.text;
            }
            if (item.content) {
              return this.resolveContent(item);
            }
            return '';
          })
          .filter(Boolean)
          .join('\n\n');
      };

      if (!event) {
        return '';
      }
      if (typeof event === 'string') {
        return event;
      }
      if (typeof event.content === 'string') {
        return event.content;
      }
      if (Array.isArray(event.content)) {
        return mapContentArray(event.content);
      }
      if (event.data) {
        if (typeof event.data === 'string') {
          return event.data;
        }
        if (event.data.content) {
          if (typeof event.data.content === 'string') {
            return event.data.content;
          }
          if (Array.isArray(event.data.content)) {
            return mapContentArray(event.data.content);
          }
        }
      }
      if (event.message && event.message.content) {
        if (typeof event.message.content === 'string') {
          return event.message.content;
        }
        if (Array.isArray(event.message.content)) {
          return mapContentArray(event.message.content);
        }
      }
      if (event.delta && typeof event.delta === 'string') {
        return event.delta;
      }
      if (event.delta && event.delta.content) {
        return Array.isArray(event.delta.content)
          ? mapContentArray(event.delta.content)
          : String(event.delta.content || '');
      }
      return '';
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
    }
  }
};
</script>

<style scoped>
.document-chat {
  min-height: 28rem;
}

.chat-header__icon {
  width: 2.5rem;
  height: 2.5rem;
  background-color: rgba(13, 110, 253, 0.1);
  color: #0d6efd;
  font-size: 1.1rem;
}

.chat-bubble {
  max-width: 75%;
  border-radius: 1rem;
  padding: 0.75rem 1rem;
  box-shadow: 0 0.25rem 0.75rem rgba(0, 0, 0, 0.05);
}

.chat-bubble-user {
  border-bottom-right-radius: 0.25rem;
}

.chat-bubble-agent {
  border-bottom-left-radius: 0.25rem;
}

.chat-content {
  white-space: pre-wrap;
}

.chat-enter-active,
.chat-leave-active {
  transition: all 0.2s ease;
}

.chat-enter-from,
.chat-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.chat-input textarea {
  resize: none;
}
</style>
