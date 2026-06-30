<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import { Slider } from '$lib/components/ui/slider';
	import type { ScaleMode } from '$lib/types';
	import HelpButton from './HelpButton.svelte';
	import { helpFor } from './help';

	let {
		scaleMode = $bindable<ScaleMode>(),
		manualScale = $bindable(4),
		minScale = $bindable(2),
		maxScale = $bindable(16),
		confidenceThreshold = $bindable(0.45),
		originalWidth = $bindable<number | undefined>(),
		originalHeight = $bindable<number | undefined>(),
		selectedFile,
		isProcessing,
		isCancelling,
		statusMessage,
		warningMessage,
		errorMessage,
		onRestore,
		onCancel
	}: {
		scaleMode: ScaleMode;
		manualScale: number;
		minScale: number;
		maxScale: number;
		confidenceThreshold: number;
		originalWidth: number | undefined;
		originalHeight: number | undefined;
		selectedFile: File | null;
		isProcessing: boolean;
		isCancelling: boolean;
		statusMessage: string;
		warningMessage: string | null;
		errorMessage: string | null;
		onRestore: () => void;
		onCancel: () => void;
	} = $props();

	function modeClass(active: boolean) {
		return active
			? 'border-[rgba(248,221,164,0.72)] bg-[rgba(223,137,56,0.16)] text-[var(--color-text)]'
			: 'border-[var(--color-border)] bg-[rgba(47,38,48,0.52)] text-[var(--color-text-muted)]';
	}
</script>

<section class="rounded-[1.75rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-panel)] backdrop-blur md:p-7" aria-labelledby="settings-title">
	<div class="mb-5 flex items-end justify-between gap-4">
		<p class="text-xl uppercase tracking-[0.18em] text-[var(--color-accent)]">Step 2</p>
		<h2 id="settings-title" class="text-4xl">Settings</h2>
	</div>

	<div class="grid gap-4 rounded-[1.35rem] bg-[var(--color-surface-soft)] p-5">
		<h3 class="m-0 text-2xl uppercase tracking-[0.14em]">Basic</h3>
		<div class="grid gap-2">
			<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
				<span>Scale mode</span>
				<HelpButton help={helpFor('scale-mode-help')} />
			</div>
			<div class="grid grid-cols-1 gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Scale mode">
				<label class={[modeClass(scaleMode === 'auto'), 'flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-2xl border px-4 text-xl']}>
					<input type="radio" bind:group={scaleMode} value="auto" disabled={isProcessing} />
					Auto detect
				</label>
				<label class={[modeClass(scaleMode === 'manual'), 'flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-2xl border px-4 text-xl']}>
					<input type="radio" bind:group={scaleMode} value="manual" disabled={isProcessing} />
					Manual scale
				</label>
			</div>
		</div>

		{#if scaleMode === 'manual'}
			<label class="grid gap-2">
				<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
					<span>Manual scale</span>
					<HelpButton help={helpFor('manual-scale-help')} />
				</div>
				<Slider min={2} max={16} step={1} bind:value={manualScale} disabled={isProcessing} />
				<strong class="text-2xl text-[var(--color-accent-strong)]">{manualScale}x</strong>
			</label>
		{:else}
			<p class="readable-copy m-0 leading-7 text-[var(--color-text-muted)]">
				Auto mode runs immediately and reports warnings in the PixelReForge interface when detection confidence is low.
			</p>
		{/if}
	</div>

	<details class="mt-4 rounded-[1.35rem] bg-[var(--color-surface-soft)] p-5">
		<summary class="cursor-pointer text-2xl font-black uppercase tracking-[0.14em]">Advanced</summary>

		<div class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
			<label class="grid gap-2">
				<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
					<span>Min scale</span>
					<HelpButton help={helpFor('auto-range-help')} />
				</div>
				<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" type="number" min="1" max={maxScale} bind:value={minScale} disabled={isProcessing} />
			</label>
			<label class="grid gap-2">
				<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
					<span>Max scale</span>
					<HelpButton help={helpFor('auto-range-help')} />
				</div>
				<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" type="number" min={minScale} max="64" bind:value={maxScale} disabled={isProcessing} />
			</label>
		</div>

		<label class="mt-4 grid gap-2">
			<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
				<span>Confidence threshold</span>
				<HelpButton help={helpFor('confidence-help')} />
			</div>
			<Slider min={0} max={1} step={0.05} bind:value={confidenceThreshold} disabled={isProcessing} />
			<strong class="text-2xl text-[var(--color-accent-strong)]">{confidenceThreshold.toFixed(2)}</strong>
		</label>

		<div class="mt-4 grid grid-cols-1 gap-4 opacity-80 sm:grid-cols-2" aria-label="Original size override planned for next algorithm">
			<label class="grid gap-2">
				<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
					<span>Original width</span>
					<HelpButton help={helpFor('original-size-help')} />
				</div>
				<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)] disabled:opacity-55" type="number" min="1" bind:value={originalWidth} disabled placeholder="v2" />
			</label>
			<label class="grid gap-2">
				<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
					<span>Original height</span>
					<HelpButton help={helpFor('original-size-help')} />
				</div>
				<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)] disabled:opacity-55" type="number" min="1" bind:value={originalHeight} disabled placeholder="v2" />
			</label>
		</div>
	</details>

	<div class="mt-5 flex flex-col gap-3 sm:flex-row">
		<Button class="flex-1 tracking-[0.12em]" size="lg" disabled={!selectedFile || isProcessing} onclick={onRestore}>
			{isProcessing ? 'Restoring...' : 'Restore image'}
		</Button>
		{#if isProcessing}
			<Button variant="danger" size="lg" class="tracking-[0.12em]" disabled={isCancelling} onclick={onCancel}>
				{isCancelling ? 'Cancelling...' : 'Cancel'}
			</Button>
		{/if}
	</div>

	<p class="readable-copy mt-4 leading-7 text-[var(--color-text-muted)]" aria-live="polite">{statusMessage}</p>
	{#if warningMessage}
		<p class="readable-copy mt-3 leading-7 text-[var(--color-accent-strong)]">{warningMessage}</p>
	{/if}
	{#if errorMessage}
		<p class="readable-copy mt-3 leading-7 text-[var(--color-danger-text)]">{errorMessage}</p>
	{/if}
</section>
