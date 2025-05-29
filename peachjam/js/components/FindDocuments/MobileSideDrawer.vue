<template>
  <div class="mobile-side-drawer">
    <div class="mobile-side-drawer__desktop-view d-none d-lg-block">
      <slot />
    </div>
    <div :class="`${open ? 'active' : ''} mobile-side-drawer__mobile-view d-lg-none`">
      <div class="mobile-side-drawer__mobile-view__content">
        <div
          class="overlay"
          @click="$emit('outside-drawer-click')"
        />
        <div class="slot bg-light">
          <slot />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MobileFacetsDrawer',
  props: {
    open: {
      type: Boolean,
      default: false
    }
  },
  emits: ['outside-drawer-click']
};
</script>

<style scoped>
.mobile-side-drawer__mobile-view {
  position: fixed;
  top: 0;
  left: 0;
  height: 100%;
  width: 100%;
  z-index: 99;
  visibility: hidden;
  transition: visibility 300ms ease-in-out;
}

.mobile-side-drawer__mobile-view__content {
  width: 100%;
  height: 100%;
  position: relative;
}

.mobile-side-drawer__mobile-view__content .slot {
  width: 85%;
  height: 100%;
  transition: transform 300ms ease-in-out;
  transform: translateX(-100%);
  overflow: auto;
}

.mobile-side-drawer__mobile-view__content .overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  transition: opacity 300ms ease-in-out;
  opacity: 0;
}

.mobile-side-drawer__mobile-view.active {
  visibility: visible;
}

.mobile-side-drawer__mobile-view.active .slot {
  transform: translateX(0);
}
.mobile-side-drawer__mobile-view.active .overlay {
  opacity: 1;
}
</style>
