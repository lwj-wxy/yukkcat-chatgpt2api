<template>
  <MetaChip
    :tone="quotaTone"
    size="xs"
    strong
    chip-class="min-w-[2.75rem] font-mono tabular-nums"
  >
    {{ quotaText }}
  </MetaChip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Account } from '@/api/accounts'
import MetaChip from './MetaChip.vue'

const props = defineProps<{
  account: Account
}>()

const quotaText = computed(() => props.account.quota_label)

const quotaTone = computed(() => {
  if (props.account.quota_state === 'exhausted' || props.account.quota_state === 'unknown') return 'danger'
  return 'success'
})
</script>
