<template>
  <div>
    <annotation-item
      v-for="annotation in items"
      :key="annotation.id"
      :ref="'annotation-' + annotation.id"
      :annotation-data="annotation"
      :view-root="viewRoot"
      :gutter="gutter"
      :editable="editable"
      @remove-annotation="removeAnnotation"
    />

    <div ref="permissionModal" class="modal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              {{ $t('Permission required') }}
            </h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            />
          </div>
          <div class="modal-body">
            <p>{{ $t('You cannot add a comment. ') }}</p>
            <p v-if="subscriptionProduct">
              {{ $t('To add a comment, please subscribe to ') }}{{ subscriptionProduct }}
            </p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('Close') }}
            </button>
            <a :href="loginUrl" type="button" class="btn btn-primary">{{ $t('Log in') }}</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import AnnotationItem from './Annotation.vue';
import { Modal } from 'bootstrap';
import peachJam from '../../peachjam';

export default {
  name: 'AnnotationsList',
  components: {
    AnnotationItem
  },
  props: {
    viewRoot: HTMLElement,
    gutter: HTMLElement,
    editable: Boolean,
    subscriptionProduct: {
      type: String,
      default: ''
    }
  },
  data: () => ({
    items: [],
    counter: -1,
    user: null,
    editable: false
  }),
  computed: {
    loginUrl () {
      return '/accounts/login/?next=' + encodeURIComponent(window.location.pathname + window.location.search + window.location.hash);
    }
  },
  mounted () {
    peachJam.whenUserLoaded().then((user) => {
      if (user.perms.includes('peachjam.add_annotation')) {
        this.editable = true;
        this.getAnnotations();
      }
    });
  },
  methods: {
    async getAnnotations () {
      if (!this.editable) return;
      try {
        const resp = await fetch(`/api/documents/${this.viewRoot.dataset.documentId}/annotations/`);
        if (resp.ok) {
          this.items = (await resp.json()).results;
        }
      } catch {
        // ignore network errors
      }
    },
    addAnnotation (target) {
      if (!this.editable) {
        const permissionModal = new Modal(this.$refs.permissionModal);
        permissionModal.show();
        return;
      }
      const newAnnotation = {
        id: this.counter--,
        text: '',
        target_selectors: target.selectors,
        target_id: target.anchor_id,
        document: this.viewRoot.dataset.documentId,
        user: window.peachjam.user.name
      };
      this.items.push(newAnnotation);
      this.$nextTick(() => {
        this.$refs['annotation-' + newAnnotation.id][0].focusTextArea();
      });
    },
    async removeAnnotation (annotation) {
      this.items = this.items.filter((item) => item !== annotation);
    }
  }
};
</script>
