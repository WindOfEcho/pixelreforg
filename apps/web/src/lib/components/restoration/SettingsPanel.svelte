<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import { Slider } from '$lib/components/ui/slider';
	import { RESTORE_ALGORITHM_OPTIONS, algorithmOptionFor, supportsColorBucketControls, supportsFractionalControls, supportsScaleControls } from '$lib/restoration/algorithms';
	import type { PaletteCleanupMode, RestoreAlgorithm, ScaleMode } from '$lib/types';
	import HelpButton from './HelpButton.svelte';
	import { helpFor } from './help';

	let {
		algorithm = $bindable<RestoreAlgorithm>(),
		scaleMode = $bindable<ScaleMode>(),
		manualScale = $bindable(4),
		minScale = $bindable(2),
		maxScale = $bindable(16),
		originalWidth = $bindable<number | undefined>(),
		originalHeight = $bindable<number | undefined>(),
		paletteCleanup = $bindable<PaletteCleanupMode>(),
		paletteMergeDistance = $bindable(18),
		paletteTargetColors = $bindable<number | undefined>(),
		noisyColorBucketSize = $bindable(16),
		fractionalScaleStep = $bindable(0.25),
		selectedFile,
		isProcessing,
		isCancelling,
		statusMessage,
		warningMessage,
		errorMessage,
		onRestore,
		onCancel
	}: {
		algorithm: RestoreAlgorithm;
		scaleMode: ScaleMode;
		manualScale: number;
		minScale: number;
		maxScale: number;
		originalWidth: number | undefined;
		originalHeight: number | undefined;
		paletteCleanup: PaletteCleanupMode;
		paletteMergeDistance: number;
		paletteTargetColors: number | undefined;
		noisyColorBucketSize: number;
		fractionalScaleStep: number;
		selectedFile: File | null;
		isProcessing: boolean;
		isCancelling: boolean;
		statusMessage: string;
		warningMessage: string | null;
		errorMessage: string | null;
		onRestore: () => void;
		onCancel: () => void;
	} = $props();

	const settingCardClass = 'grid gap-3 rounded-[1.25rem] bg-[rgba(47,38,48,0.42)] p-4';

	function modeClass(active: boolean) {
		return active
			? 'border-[rgba(248,221,164,0.72)] bg-[rgba(223,137,56,0.16)] text-[var(--color-text)]'
			: 'border-[var(--color-border)] bg-[rgba(47,38,48,0.52)] text-[var(--color-text-muted)]';
	}

	let selectedAlgorithm = $derived(algorithmOptionFor(algorithm));
</script>

<section class="rounded-[1.75rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-panel)] backdrop-blur md:p-7" aria-labelledby="settings-title">
	<div class="mb-5 flex items-end justify-between gap-4">
		<p class="text-xl uppercase tracking-[0.18em] text-[var(--color-accent)]">Step 2</p>
		<h2 id="settings-title" class="text-4xl">Settings</h2>
	</div>

	<div class="grid gap-4 rounded-[1.35rem] bg-[var(--color-surface-soft)] p-5">
		<h3 class="m-0 text-2xl uppercase tracking-[0.14em]">Basic</h3>
		<div class={settingCardClass}>
			<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
				<span>Algorithm</span>
			</div>
			<div class="grid grid-cols-1 gap-2 md:grid-cols-2" role="radiogroup" aria-label="Restore algorithm">
				{#each RESTORE_ALGORITHM_OPTIONS as option (option.id)}
					<label class={[modeClass(algorithm === option.id), 'flex min-h-12 cursor-pointer flex-col justify-center gap-1 rounded-2xl border px-4 py-3 text-xl']}>
						<span class="flex items-center gap-2"><input type="radio" bind:group={algorithm} value={option.id} disabled={isProcessing} /> {option.label} <HelpButton help={helpFor(option.helpId)} /></span>
						<small class="readable-copy text-sm text-[var(--color-text-muted)]">{option.shortDescription}</small>
					</label>
				{/each}
			</div>

			{#if selectedAlgorithm}
				<p class="readable-copy m-0 leading-7 text-[var(--color-text-muted)]">
					{selectedAlgorithm.description}
				</p>
			{/if}
		</div>

		{#if supportsColorBucketControls(algorithm)}
			<label class={settingCardClass}>
				<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
					<span>Color bucket size</span>
					<HelpButton help={helpFor('noisy-bucket-help')} />
				</div>
				<Slider min={4} max={32} step={2} bind:value={noisyColorBucketSize} disabled={isProcessing} />
				<strong class="text-2xl text-[var(--color-accent-strong)]">{noisyColorBucketSize}</strong>
			</label>
		{/if}

		{#if supportsScaleControls(algorithm)}
			<div class={settingCardClass}>
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
				{#if scaleMode === 'auto'}
					<p class="readable-copy m-0 leading-7 text-[var(--color-text-muted)]">
						Auto scale detection runs immediately and reports warnings when confidence is low.
					</p>
				{/if}
			</div>

			{#if scaleMode === 'manual'}
				<label class={settingCardClass}>
					<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
						<span>Manual scale</span>
						<HelpButton help={helpFor('manual-scale-help')} />
					</div>
					<Slider min={1} max={16} step={supportsFractionalControls(algorithm) ? 0.25 : 1} bind:value={manualScale} disabled={isProcessing} />
					<div class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
						<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" type="number" min="1" max="64" step={supportsFractionalControls(algorithm) ? 0.01 : 1} bind:value={manualScale} disabled={isProcessing} />
						<strong class="text-2xl text-[var(--color-accent-strong)]">x</strong>
					</div>
				</label>
			{/if}
		{/if}

		<label class={settingCardClass}>
			<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
				<span>Palette cleanup</span>
				<HelpButton help={helpFor('palette-cleanup-help')} />
			</div>
			<select class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" bind:value={paletteCleanup} disabled={isProcessing}>
				<option value="off">Off</option>
				<option value="light">Light</option>
				<option value="medium">Medium</option>
				<option value="strong">Strong</option>
				<option value="custom">Custom</option>
			</select>
			<p class="readable-copy m-0 text-sm leading-6 text-[var(--color-text-muted)]">Light, medium, and strong merge near-duplicate colors after restoration. Use stronger cleanup for noisy JPEG or AI color artifacts.</p>
		</label>

		{#if paletteCleanup === 'custom'}
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<label class={settingCardClass}>
					<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
						<span>Merge distance</span>
						<HelpButton help={helpFor('palette-merge-distance-help')} />
					</div>
					<Slider min={0} max={64} step={1} bind:value={paletteMergeDistance} disabled={isProcessing} />
					<strong class="text-2xl text-[var(--color-accent-strong)]">{paletteMergeDistance}</strong>
				</label>
				<label class={settingCardClass}>
					<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
						<span>Target colors</span>
						<HelpButton help={helpFor('palette-target-colors-help')} />
					</div>
					<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" type="number" min="1" max="256" bind:value={paletteTargetColors} disabled={isProcessing} placeholder="optional" />
				</label>
			</div>
		{/if}
	</div>

	{#if supportsScaleControls(algorithm)}
		<details class="mt-4 rounded-[1.35rem] bg-[var(--color-surface-soft)] p-5">
			<summary class="cursor-pointer text-2xl font-black uppercase tracking-[0.14em]">Advanced</summary>

			<div class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
				<label class={settingCardClass}>
					<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
						<span>Min scale</span>
						<HelpButton help={helpFor('auto-range-help')} />
					</div>
					<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" type="number" min="1" max={maxScale} bind:value={minScale} disabled={isProcessing} />
				</label>
				<label class={settingCardClass}>
					<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
						<span>Max scale</span>
						<HelpButton help={helpFor('auto-range-help')} />
					</div>
					<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" type="number" min={minScale} max="64" bind:value={maxScale} disabled={isProcessing} />
				</label>
			</div>

			{#if supportsFractionalControls(algorithm)}
				<div class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2" aria-label="Original size override">
					<label class={settingCardClass}>
						<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
							<span>Original width</span>
							<HelpButton help={helpFor('original-size-help')} />
						</div>
						<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)] disabled:opacity-55" type="number" min="1" bind:value={originalWidth} disabled={isProcessing} placeholder="optional" />
					</label>
					<label class={settingCardClass}>
						<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
							<span>Original height</span>
							<HelpButton help={helpFor('original-size-help')} />
						</div>
						<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)] disabled:opacity-55" type="number" min="1" bind:value={originalHeight} disabled={isProcessing} placeholder="optional" />
					</label>
				</div>

				<label class={[settingCardClass, 'mt-4']}>
					<div class="readable-copy flex items-center gap-2 text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">
						<span>Fractional step</span>
						<HelpButton help={helpFor('fractional-step-help')} />
					</div>
					<Slider min={0.05} max={1} step={0.05} bind:value={fractionalScaleStep} disabled={isProcessing} />
					<strong class="text-2xl text-[var(--color-accent-strong)]">{fractionalScaleStep.toFixed(2)}</strong>
				</label>
			{/if}
		</details>
	{/if}

	<div class="mt-5 flex flex-col gap-3 sm:flex-row">
		<Button class="flex-1" size="lg" disabled={!selectedFile || isProcessing} onclick={onRestore}>
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
