<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import { buttonClass, type Variant, type Size } from './button.styles';

	let {
		class: className,
		variant = 'primary',
		size = 'md',
		children,
		...rest
	}: HTMLButtonAttributes & {
		variant?: Variant;
		size?: Size;
		children?: Snippet;
	} = $props();
</script>

<button class={buttonClass(variant, size, className)} {...rest}>
	{@render children?.()}
</button>
