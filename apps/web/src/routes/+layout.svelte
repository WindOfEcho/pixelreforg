<script lang="ts">
	import * as Tooltip from '$lib/components/ui/tooltip';
	import favicon from '$lib/assets/favicon.svg';
	import '$lib/styles/theme.css';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<Tooltip.Provider delayDuration={180}>
	{@render children()}
</Tooltip.Provider>
