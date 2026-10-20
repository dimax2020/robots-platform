<template>
  <div>
    <NuxtRouteAnnouncer />
    <!-- Полоса сверху при переходе между страницами: видно, что клик сработал и страница грузится. -->
    <NuxtLoadingIndicator color="#12a36d" :height="3" :throttle="100" />
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </div>
</template>
