<script lang="ts">
	import * as Tooltip from '$lib/components/ui/tooltip';
	import type { HelpText } from '$lib/ui/types';

	let { help }: { help: HelpText } = $props();
</script>

<Tooltip.Root>
	<Tooltip.Trigger
		class="inline-flex size-6 cursor-help items-center justify-center rounded-full border border-[var(--color-border-strong)] bg-[rgba(248,221,164,0.12)] p-0 font-sans text-xs font-bold leading-none text-[var(--color-accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent-strong)]"
		aria-label={`Help: ${help.label}`}
	>
		?
	</Tooltip.Trigger>
	<Tooltip.Portal>
		<Tooltip.Content
			class="readable-copy z-50 grid w-[min(20rem,78vw)] gap-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-deep)] p-4 text-xs font-normal normal-case leading-5 tracking-normal text-[var(--color-text-muted)] shadow-[var(--shadow-popover)]"
			sideOffset={8}
		>
			<strong class="text-xs font-semibold normal-case tracking-normal text-[var(--color-text)]">{help.label}</strong>
			<span>{help.description}</span>
			{#if help.impact}
				<span>Impact: {help.impact}</span>
			{/if}
			{#if help.example}
				<span>Example: {help.example}</span>
			{/if}
		</Tooltip.Content>
	</Tooltip.Portal>
</Tooltip.Root>
