<template>
  <div
    class="modal fade"
    tabindex="-1"
    role="dialog"
    aria-hidden="true"
  >
    <div
      class="modal-dialog"
      role="document"
    >
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">
            {{ $t('Share') }}
          </h5>
          <button
            type="button"
            class="btn-close"
            data-bs-dismiss="modal"
            aria-label="Close"
          />
        </div>

        <div class="modal-body">
          <p>{{ text }}</p>
          <div class="d-flex align-items-center">
            <a
              :href="`https://api.whatsapp.com/send?text=${ combined }`"
              class="btn btn-link"
              target="_blank"
              data-track-event="Document | Social share | WhatsApp"
              @click="modal.hide()"
            ><i class="bi bi-whatsapp whatsapp-forecolor share-icon" />
            </a>
            <a
              :href="`https://twitter.com/intent/tweet?text=${ combined }`"
              class="btn btn-link"
              target="_blank"
              data-track-event="Document | Social share | X"
              @click="modal.hide()"
            ><i class="bi bi-twitter-x twitter-x-forecolor share-icon" />
            </a>
            <a
              :href="`https://www.facebook.com/sharer/sharer.php?u=${ encodeURIComponent(url) }`"
              class="btn btn-link"
              target="_blank"
              data-track-event="Document | Social share | Facebook"
              @click="modal.hide()"
            ><i class="bi bi-facebook facebook-forecolor share-icon" />
            </a>
            <a
              :href="`https://www.linkedin.com/sharing/share-offsite/?url=${ encodeURIComponent(url) }`"
              class="btn btn-link"
              target="_blank"
              data-track-event="Document | Social share | LinkedIn"
              @click="modal.hide()"
            ><i class="bi bi-linkedin linkedin-forecolor share-icon" />
            </a>
            <a
              :href="`mailto:?subject=${emailSubject}&body=${combined}`"
              class="btn btn-link"
              target="_blank"
              data-track-event="Document | Social share | Email"
              @click="modal.hide()"
            ><i class="bi bi-envelope-at-fill envelope-at-fill-forecolor share-icon" />
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>

export default {
  name: 'ShareSelectionModal',
  props: ['text', 'url'],

  computed: {
    combined () {
      return encodeURIComponent(`${this.text} ${this.url}`);
    },
    emailSubject () {
      const emailShare = document.querySelector('#email-share');
      if (emailShare) {
        return emailShare.getAttribute('data-subject');
      }
      return '';
    }
  },

  mounted () {
    document.body.appendChild(this.$el);
    this.modal = new window.bootstrap.Modal(this.$el);
    this.$el.addEventListener('hidden.bs.modal', () => {
      this.$el.remove();
    });
    this.modal.show();
  }
};
</script>
