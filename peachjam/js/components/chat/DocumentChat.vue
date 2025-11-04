<template>
  <div class="document-chat d-flex flex-column h-100">
    <div ref="messageContainer" class="chat-messages flex-grow-1 overflow-auto p-2">
      <div v-if="messages.length === 0 && !loading" class="text-center text-muted py-5">
        Start the conversation by asking a question about this document.
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
            <div v-if="message.role === 'ai'">
              <button class="btn btn-sm btn-outline-secondary border-0" title="Upvote message" @click="voteUp(message.id)">
                <i v-if="votingUp === message.id" class="bi bi-check"></i>
                <i v-else class="bi bi-hand-thumbs-up"></i>
              </button>
              <button class="btn btn-sm btn-outline-secondary border-0 ms-1" title="Downvote message" @click="voteDown(message.id)">
                <i v-if="votingDown === message.id" class="bi bi-check"></i>
                <i v-else class="bi bi-hand-thumbs-down"></i>
              </button>
            </div>
          </div>
        </div>
      </transition-group>

      <div v-if="loading" class="d-flex justify-content-start mb-3">
        <div class="chat-bubble chat-bubble-agent text-muted d-flex align-items-center gap-2">
          <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
          <span>Thinking…</span>
        </div>
      </div>

      <div v-if="error" class="alert alert-warning">{{ error }}</div>
    </div>

    <form class="chat-input p-2" @submit.prevent="submit" novalidate>
      <div class="input-group">
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
        <button class="btn btn-primary" type="submit" :disabled="loading || !isReady" title="Send">
          <i v-if="!loading" class="bi bi-send"></i>
          <span v-else class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
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
      inputText: '',
      loading: false,
      error: null,
      votingUp: null,
      votingDown: null
    };
  },
  computed: {
    isReady () {
      return this.inputText.trim().length > 0;
    }
  },
  mounted () {
    this.load();
    this.focusInput();
  },
  methods: {
    async load (isNew) {
      try {
        const url = `${peachJam.config.urlLangPrefix}/api/documents/${this.documentId}/chat` + (isNew ? '?new' : '');
        const resp = await fetch(url, {
          method: 'POST',
          headers: {
            'X-CSRFToken': await csrfToken()
          }
        });
        if (!resp.ok) {
          throw new Error('The assistant could not respond right now. Please try again.');
        }
        const data = await resp.json();
        this.threadId = data.thread_id;
        this.mergeMessages(data.messages);
        this.$nextTick(() => {
          this.scrollToBottom();
          this.focusInput();
        });
      } catch (err) {
        console.error(err);
        this.error = err.message || 'Something went wrong. Please try again.';
      }
    },
    async submit () {
      if (this.loading || !this.isReady || !this.threadId) {
        return;
      }

      const text = this.inputText.trim();
      if (!text) {
        return;
      }

      const userMessage = this.createMessage('human', text);
      this.messages.push(userMessage);
      this.inputText = '';
      this.loading = true;
      this.error = null;

      this.$nextTick(() => {
        this.focusInput();
        this.scrollToBottom();
      });

      try {
        const payload = {
          message: userMessage
        };

        const resp = await fetch(`${peachJam.config.urlLangPrefix}/api/chats/${this.threadId}`, {
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
        this.mergeMessages(data.messages);
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
          if (msg.role === 'ai') {
            // parse markdown
            msg.content_html = marked.parse(msg.content);
          }
          this.messages.push({ ...msg });
        }
      }
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
      // start a new chat
      this.messages.splice(0, this.messages.length);
      this.error = null;
      this.threadId = null;
      this.load(true);
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
    }
  }
};
</script>

<style scoped>
</style>
