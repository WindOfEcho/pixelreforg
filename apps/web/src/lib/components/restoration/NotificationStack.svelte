<script lang="ts">
	import type { UiNotification } from '$lib/ui/types';

	let {
		notifications,
		onDismiss
	}: {
		notifications: UiNotification[];
		onDismiss: (id: number) => void;
	} = $props();
</script>

{#if notifications.length > 0}
	<section class="notification-stack" aria-label="Interface messages" aria-live="polite">
		{#each notifications as notification (notification.id)}
			<article class={`notification ${notification.tone}`}>
				<div>
					<strong>{notification.title}</strong>
					<p>{notification.message}</p>
				</div>
				<button type="button" aria-label="Dismiss notification" onclick={() => onDismiss(notification.id)}>
					Close
				</button>
			</article>
		{/each}
	</section>
{/if}
