<template>
  <div class="flynote-manager">
    <section
      class="flynote-manager__pane flynote-manager__pane--list"
      aria-labelledby="main-page-heading"
    >
      <h1 id="main-page-heading" class="h4 mb-3">
        Flynote manager
      </h1>
    </section>
    <section
      class="flynote-manager__pane flynote-manager__pane--detail"
      aria-label="Flynote details"
    ></section>
  </div>
</template>

<script>
export default {
  name: 'FlynoteManager'
};
</script>

<style scoped>
.flynote-manager {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
}

.flynote-manager__pane {
  min-height: 0;
  overflow-y: auto;
  padding: 1rem;
}

.flynote-manager__pane--list {
  flex: 0 0 22rem;
  border-right: 1px solid var(--bs-border-color);
}

.flynote-manager__pane--detail {
  flex: 1 1 auto;
}
</style>
