<template>
  <span v-if="userHelpLink">
    <a
      :href="`${userHelpLink}${page}`"
      class="me-3"
      target="_blank"
    ><i class="bi bi-question-circle me-1" />{{ $t('Help') }}</a>
  </span>
</template>

<script>
import peachjam from '../peachjam';

export default {
  name: 'HelpBtn',
  props: ['page'],
  data: () => {
    return {
      userHelpLink: peachjam.config.userHelpLink
    };
  }
};
</script>
