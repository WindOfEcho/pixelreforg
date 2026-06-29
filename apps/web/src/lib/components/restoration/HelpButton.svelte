<script lang="ts">
	import type { HelpText } from '$lib/ui/types';

	let { help }: { help: HelpText } = $props();
</script>

<span class="help-wrap">
	<button class="help-button" type="button" aria-describedby={help.id}>?</button>
	<span class="tooltip" id={help.id} role="tooltip">
		<strong>{help.label}</strong>
		<span>{help.description}</span>
		<span>Impact: {help.impact}</span>
		<span>Example: {help.example}</span>
	</span>
</span>
