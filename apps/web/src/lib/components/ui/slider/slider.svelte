<script lang="ts">
	import { Slider as SliderPrimitive } from 'bits-ui';
	import { cn } from '$lib/utils';

	let {
		id,
		class: className,
		value = $bindable(0),
		min = 0,
		max = 100,
		step = 1,
		disabled = false
	}: {
		id?: string;
		class?: string;
		value?: number;
		min?: number;
		max?: number;
		step?: number;
		disabled?: boolean;
	} = $props();
</script>

<SliderPrimitive.Root
	{id}
	type="single"
	bind:value
	{min}
	{max}
	{step}
	{disabled}
	class={cn('relative flex w-full touch-none select-none items-center py-2 data-[disabled]:opacity-55', className)}
>
	<span class="relative h-2 w-full grow overflow-hidden rounded-full bg-[rgba(251,242,223,0.16)]">
		<SliderPrimitive.Range class="absolute h-full bg-[var(--color-action)]" />
	</span>
	<SliderPrimitive.Thumb index={0} class="block size-5 rounded-full border-2 border-[var(--color-accent-strong)] bg-[var(--color-bg-deep)] shadow-[var(--shadow-popover)] transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent-strong)] disabled:pointer-events-none" />
</SliderPrimitive.Root>
