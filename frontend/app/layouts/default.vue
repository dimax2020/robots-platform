<template>
  <div class="layout">
    <AppNavbar />
    <main class="main">
      <slot />
    </main>
    <AppFooter />
    <CompareBar />
  </div>
</template>

<style scoped>
.layout { min-height: 100dvh; display: flex; flex-direction: column; }
.main { flex: 1; }
</style>
