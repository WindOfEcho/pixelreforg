<script lang="ts">
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
</script>

<section class="panel settings-panel" aria-labelledby="settings-title">
	<div class="section-header">
		<p>Step 2</p>
		<h2 id="settings-title">Settings</h2>
	</div>

	<div class="settings-group">
		<h3>Basic</h3>
		<div class="field-block">
			<div class="field-heading">
				<span>Scale mode</span>
				<HelpButton help={helpFor('scale-mode-help')} />
			</div>
			<div class="segmented" role="radiogroup" aria-label="Scale mode">
				<label class:active={scaleMode === 'auto'}>
					<input type="radio" bind:group={scaleMode} value="auto" disabled={isProcessing} />
					Auto detect
				</label>
				<label class:active={scaleMode === 'manual'}>
					<input type="radio" bind:group={scaleMode} value="manual" disabled={isProcessing} />
					Manual scale
				</label>
			</div>
		</div>

		{#if scaleMode === 'manual'}
			<label class="field-block">
				<div class="field-heading">
					<span>Manual scale</span>
					<HelpButton help={helpFor('manual-scale-help')} />
				</div>
				<input type="range" min="2" max="16" step="1" bind:value={manualScale} disabled={isProcessing} />
				<strong class="value-readout">{manualScale}x</strong>
			</label>
		{:else}
			<p class="notice">
				Auto mode runs immediately and reports warnings in the PixelReForge interface when detection confidence is low.
			</p>
		{/if}
	</div>

	<details class="settings-group advanced-group">
		<summary>Advanced</summary>

		<div class="field-grid">
			<label class="field-block">
				<div class="field-heading">
					<span>Min scale</span>
					<HelpButton help={helpFor('auto-range-help')} />
				</div>
				<input type="number" min="1" max={maxScale} bind:value={minScale} disabled={isProcessing} />
			</label>
			<label class="field-block">
				<div class="field-heading">
					<span>Max scale</span>
					<HelpButton help={helpFor('auto-range-help')} />
				</div>
				<input type="number" min={minScale} max="64" bind:value={maxScale} disabled={isProcessing} />
			</label>
		</div>

		<label class="field-block">
			<div class="field-heading">
				<span>Confidence threshold</span>
				<HelpButton help={helpFor('confidence-help')} />
			</div>
			<input type="range" min="0" max="1" step="0.05" bind:value={confidenceThreshold} disabled={isProcessing} />
			<strong class="value-readout">{confidenceThreshold.toFixed(2)}</strong>
		</label>

		<div class="field-grid muted-grid" aria-label="Original size override planned for next algorithm">
			<label class="field-block">
				<div class="field-heading">
					<span>Original width</span>
					<HelpButton help={helpFor('original-size-help')} />
				</div>
				<input type="number" min="1" bind:value={originalWidth} disabled placeholder="v2" />
			</label>
			<label class="field-block">
				<div class="field-heading">
					<span>Original height</span>
					<HelpButton help={helpFor('original-size-help')} />
				</div>
				<input type="number" min="1" bind:value={originalHeight} disabled placeholder="v2" />
			</label>
		</div>
	</details>

	<div class="actions">
		<button class="restore-button" disabled={!selectedFile || isProcessing} onclick={onRestore}>
			{isProcessing ? 'Restoring...' : 'Restore image'}
		</button>
		{#if isProcessing}
			<button class="cancel-button" disabled={isCancelling} onclick={onCancel}>
				{isCancelling ? 'Cancelling...' : 'Cancel'}
			</button>
		{/if}
	</div>

	<p class="status" aria-live="polite">{statusMessage}</p>
	{#if warningMessage}
		<p class="warning">{warningMessage}</p>
	{/if}
	{#if errorMessage}
		<p class="error">{errorMessage}</p>
	{/if}
</section>
