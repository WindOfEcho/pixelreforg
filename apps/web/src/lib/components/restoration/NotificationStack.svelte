<script lang="ts">
	import type { UiNotification } from '$lib/ui/types';

	let {
		notifications,
		onDismiss
	}: {
		notifications: UiNotification[];
		onDismiss: (id: number) => void;
	} = $props();

	function toneClass(tone: UiNotification['tone']) {
		return {
			info: 'border-l-[var(--color-accent-strong)]',
			warning: 'border-l-[var(--color-action)]',
			error: 'border-l-[var(--color-danger)]'
		}[tone];
	}

	function progressClass(tone: UiNotification['tone']) {
		return {
			info: 'bg-[var(--color-accent-strong)]',
			warning: 'bg-[var(--color-action)]',
			error: 'bg-[var(--color-danger)]'
		}[tone];
	}
</script>

{#if notifications.length > 0}
	<section class="fixed bottom-4 right-4 z-20 grid w-[min(26rem,calc(100vw-2rem))] gap-3" aria-label="Interface messages" aria-live="polite">
		{#each notifications as notification (notification.id)}
			<article class={[toneClass(notification.tone), 'relative overflow-hidden rounded-2xl border border-l-5 border-[var(--color-border)] bg-[var(--color-surface-strong)] p-4 shadow-[var(--shadow-popover)] backdrop-blur']}>
				<div class="flex items-start justify-between gap-4 max-sm:flex-col">
					<div>
						<strong class="block text-2xl text-[var(--color-text)]">{notification.title}</strong>
						<p class="readable-copy mt-1 leading-6 text-[var(--color-text-muted)]">{notification.message}</p>
					</div>
					<button class="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-3 py-2 text-sm font-black uppercase tracking-[0.12em] text-[var(--color-text)]" type="button" aria-label="Dismiss notification" onclick={() => onDismiss(notification.id)}>
						Close
					</button>
				</div>
				{#if notification.autoDismissMs}
					<div class="absolute inset-x-0 bottom-0 h-1 bg-[rgba(251,242,223,0.12)]" aria-hidden="true">
						<span class={[progressClass(notification.tone), 'block h-full origin-left [animation:notification-countdown_linear_forwards]']} style={`animation-duration: ${notification.autoDismissMs}ms;`}></span>
					</div>
				{/if}
			</article>
		{/each}
	</section>
{/if}
