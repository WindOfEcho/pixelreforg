<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import { Slider } from '$lib/components/ui/slider';
	import type { SpriteSheetInputMode, SpriteSheetSettings } from '$lib/types';

	let {
		settings = $bindable<SpriteSheetSettings>(),
		inputMode,
		selectedFilesCount,
		isProcessing,
		isCancelling,
		statusMessage,
		warningMessage,
		errorMessage,
		onCreate,
		onCancel
	}: {
		settings: SpriteSheetSettings;
		inputMode: SpriteSheetInputMode;
		selectedFilesCount: number;
		isProcessing: boolean;
		isCancelling: boolean;
		statusMessage: string;
		warningMessage: string | null;
		errorMessage: string | null;
		onCreate: () => void;
		onCancel: () => void;
	} = $props();

	const settingCardClass = 'grid gap-3 rounded-[1.25rem] bg-[rgba(47,38,48,0.42)] p-4';

	function modeClass(active: boolean) {
		return active
			? 'border-[rgba(248,221,164,0.72)] bg-[rgba(223,137,56,0.16)] text-[var(--color-text)]'
			: 'border-[var(--color-border)] bg-[rgba(47,38,48,0.52)] text-[var(--color-text-muted)]';
	}

	function setBackgroundMode(mode: 'transparent' | 'color') {
		settings.backgroundColor = mode === 'transparent' ? null : (settings.backgroundColor ?? '#503F4AFF');
	}
</script>

<section class="rounded-[1.75rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-panel)] backdrop-blur md:p-7" aria-labelledby="atlas-settings-title">
	<div class="mb-5 flex items-end justify-between gap-4">
		<p class="text-xl uppercase tracking-[0.18em] text-[var(--color-accent)]">Step 2</p>
		<h2 id="atlas-settings-title" class="text-4xl">Build settings</h2>
	</div>

	<div class="grid gap-4 rounded-[1.35rem] bg-[var(--color-surface-soft)] p-5">
		<h3 class="m-0 text-2xl uppercase tracking-[0.14em]">Packing</h3>
		<div class={settingCardClass}>
			<div class="readable-copy text-sm font-medium leading-5 tracking-normal text-[var(--color-text)]">Placement mode</div>
			<div class="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Sprite packing mode">
				<label class={[modeClass(settings.packingMode === 'compact'), 'flex min-h-16 cursor-pointer flex-col justify-center gap-1 rounded-2xl border px-4 py-3 text-xl']}>
					<span><input type="radio" bind:group={settings.packingMode} value="compact" disabled={isProcessing} /> Compact</span>
					<small class="readable-copy text-sm text-[var(--color-text-muted)]">Fit frames tightly with MaxRects placement.</small>
				</label>
				<label class={[modeClass(settings.packingMode === 'grid'), 'flex min-h-16 cursor-pointer flex-col justify-center gap-1 rounded-2xl border px-4 py-3 text-xl']}>
					<span><input type="radio" bind:group={settings.packingMode} value="grid" disabled={isProcessing} /> Even grid</span>
					<small class="readable-copy text-sm text-[var(--color-text-muted)]">Use uniform cells for a predictable atlas layout.</small>
				</label>
			</div>
		</div>

		<div class="grid gap-4 sm:grid-cols-3">
			<label class={settingCardClass}>
				<span class="readable-copy text-sm font-medium text-[var(--color-text)]">Padding</span>
				<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" type="number" min="0" max="64" bind:value={settings.padding} disabled={isProcessing} />
				<small class="readable-copy text-sm text-[var(--color-text-muted)]">Space between frames.</small>
			</label>
			<label class={settingCardClass}>
				<span class="readable-copy text-sm font-medium text-[var(--color-text)]">Outer border</span>
				<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" type="number" min="0" max="64" bind:value={settings.borderPadding} disabled={isProcessing} />
				<small class="readable-copy text-sm text-[var(--color-text-muted)]">Space around the atlas edge.</small>
			</label>
			<label class={settingCardClass}>
				<span class="readable-copy text-sm font-medium text-[var(--color-text)]">Extrude</span>
				<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" type="number" min="0" max="64" bind:value={settings.extrude} disabled={isProcessing} />
				<small class="readable-copy text-sm text-[var(--color-text-muted)]">Duplicate edge pixels to prevent texture seams.</small>
			</label>
		</div>

		<label class={settingCardClass}>
			<div class="flex items-center justify-between gap-4">
				<span class="readable-copy text-sm font-medium text-[var(--color-text)]">Trim transparent bounds</span>
				<input type="checkbox" bind:checked={settings.trimTransparent} disabled={isProcessing} />
			</div>
			<Slider min={0} max={254} step={1} bind:value={settings.alphaThreshold} disabled={isProcessing || !settings.trimTransparent} />
			<small class="readable-copy text-sm text-[var(--color-text-muted)]">Alpha threshold: {settings.alphaThreshold}. Pixels at or below it are treated as transparent for bounds and auto sheet detection.</small>
		</label>

		{#if settings.packingMode === 'grid'}
			<label class={settingCardClass}>
				<span class="readable-copy text-sm font-medium text-[var(--color-text)]">Grid columns</span>
				<input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" type="number" min="1" max="512" bind:value={settings.gridColumns} disabled={isProcessing} placeholder="auto" />
				<small class="readable-copy text-sm text-[var(--color-text-muted)]">Leave empty to choose the most compact regular grid within the limits.</small>
			</label>
		{/if}
	</div>

	{#if inputMode === 'sheet'}
		<details class="mt-4 rounded-[1.35rem] bg-[var(--color-surface-soft)] p-5" open>
			<summary class="cursor-pointer text-2xl font-black uppercase tracking-[0.14em]">Sheet extraction</summary>
			<div class="mt-4 grid gap-4">
				<div class="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Sheet extraction mode">
					<label class={[modeClass(settings.extractionMode === 'auto'), 'flex min-h-16 cursor-pointer flex-col justify-center gap-1 rounded-2xl border px-4 py-3 text-xl']}>
						<span><input type="radio" bind:group={settings.extractionMode} value="auto" disabled={isProcessing} /> Auto regions</span>
						<small class="readable-copy text-sm text-[var(--color-text-muted)]">Find disconnected opaque regions.</small>
					</label>
					<label class={[modeClass(settings.extractionMode === 'grid'), 'flex min-h-16 cursor-pointer flex-col justify-center gap-1 rounded-2xl border px-4 py-3 text-xl']}>
						<span><input type="radio" bind:group={settings.extractionMode} value="grid" disabled={isProcessing} /> Manual grid</span>
						<small class="readable-copy text-sm text-[var(--color-text-muted)]">Split fixed-size cells, offsets, and gaps.</small>
					</label>
				</div>
				{#if settings.extractionMode === 'grid'}
					<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
						<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Cell width</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="1" bind:value={settings.cellWidth} disabled={isProcessing} /></label>
						<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Cell height</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="1" bind:value={settings.cellHeight} disabled={isProcessing} /></label>
						<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Columns</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="1" bind:value={settings.columns} disabled={isProcessing} placeholder="auto" /></label>
						<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Rows</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="1" bind:value={settings.rows} disabled={isProcessing} placeholder="auto" /></label>
					</div>
					<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
						<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Offset X</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="0" bind:value={settings.offsetX} disabled={isProcessing} /></label>
						<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Offset Y</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="0" bind:value={settings.offsetY} disabled={isProcessing} /></label>
						<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Gap X</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="0" bind:value={settings.gapX} disabled={isProcessing} /></label>
						<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Gap Y</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="0" bind:value={settings.gapY} disabled={isProcessing} /></label>
					</div>
				{/if}
			</div>
		</details>
	{/if}

	<details class="mt-4 rounded-[1.35rem] bg-[var(--color-surface-soft)] p-5">
		<summary class="cursor-pointer text-2xl font-black uppercase tracking-[0.14em]">Atlas constraints and export</summary>
		<div class="mt-4 grid gap-4">
			<div class="grid gap-4 sm:grid-cols-2">
				<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Max width</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="1" max="8192" bind:value={settings.maxWidth} disabled={isProcessing} /></label>
				<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Max height</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="1" max="8192" bind:value={settings.maxHeight} disabled={isProcessing} /></label>
			</div>
			<div class="grid gap-4 sm:grid-cols-2">
				<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Fixed width</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="1" max={settings.maxWidth} bind:value={settings.atlasWidth} disabled={isProcessing} placeholder="automatic" /></label>
				<label class={settingCardClass}><span class="readable-copy text-sm text-[var(--color-text)]">Fixed height</span><input class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl" type="number" min="1" max={settings.maxHeight} bind:value={settings.atlasHeight} disabled={isProcessing} placeholder="automatic" /></label>
			</div>
			<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
				<label class="readable-copy flex min-h-12 items-center gap-3 rounded-2xl bg-[rgba(47,38,48,0.42)] px-4 text-[var(--color-text)]"><input type="checkbox" bind:checked={settings.powerOfTwo} disabled={isProcessing} /> Power of two</label>
				<label class="readable-copy flex min-h-12 items-center gap-3 rounded-2xl bg-[rgba(47,38,48,0.42)] px-4 text-[var(--color-text)]"><input type="checkbox" bind:checked={settings.forceSquare} disabled={isProcessing} /> Square atlas</label>
				<label class="readable-copy flex min-h-12 items-center gap-3 rounded-2xl bg-[rgba(47,38,48,0.42)] px-4 text-[var(--color-text)]"><input type="checkbox" bind:checked={settings.allowRotation} disabled={isProcessing || settings.packingMode === 'grid'} /> Allow 90° rotation</label>
				<label class="readable-copy flex min-h-12 items-center gap-3 rounded-2xl bg-[rgba(47,38,48,0.42)] px-4 text-[var(--color-text)]"><input type="checkbox" bind:checked={settings.includeMetadata} disabled={isProcessing} /> Export JSON metadata</label>
			</div>
			{#if settings.packingMode === 'grid'}<p class="readable-copy m-0 text-sm text-[var(--color-text-muted)]">Rotation is available only in compact packing because it provides no space benefit in a uniform grid.</p>{/if}
			<div class="grid gap-4 sm:grid-cols-2">
				<label class={settingCardClass}>
					<span class="readable-copy text-sm text-[var(--color-text)]">Frame ordering</span>
					<select class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" bind:value={settings.sortMode} disabled={isProcessing}>
						<option value="area">Largest area first</option>
						<option value="width">Widest first</option>
						<option value="height">Tallest first</option>
						<option value="name">Filename</option>
						<option value="input">Upload order</option>
					</select>
				</label>
				<div class={settingCardClass}>
					<label class="readable-copy text-sm text-[var(--color-text)]" for="atlas-background">Atlas background</label>
					<select id="atlas-background" class="min-h-11 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] px-3 text-2xl text-[var(--color-text)]" value={settings.backgroundColor ? 'color' : 'transparent'} onchange={(event) => setBackgroundMode((event.currentTarget as HTMLSelectElement).value as 'transparent' | 'color')} disabled={isProcessing}>
						<option value="transparent">Transparent</option>
						<option value="color">Solid color</option>
					</select>
					{#if settings.backgroundColor}
						<input class="h-11 w-full cursor-pointer rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-strong)] p-1" type="color" value={settings.backgroundColor.slice(0, 7)} onchange={(event) => (settings.backgroundColor = `${(event.currentTarget as HTMLInputElement).value}FF`)} disabled={isProcessing} aria-label="Atlas background color" />
					{/if}
				</div>
			</div>
		</div>
	</details>

	<div class="mt-5 flex flex-col gap-3 sm:flex-row">
		<Button class="flex-1" size="lg" disabled={selectedFilesCount === 0 || isProcessing} onclick={onCreate}>
			{isProcessing ? 'Packing atlas...' : 'Create sprite atlas'}
		</Button>
		{#if isProcessing}
			<Button variant="danger" size="lg" class="tracking-[0.12em]" disabled={isCancelling} onclick={onCancel}>
				{isCancelling ? 'Cancelling...' : 'Cancel'}
			</Button>
		{/if}
	</div>

	<p class="readable-copy mt-4 leading-7 text-[var(--color-text-muted)]" aria-live="polite">{statusMessage}</p>
	{#if warningMessage}<p class="readable-copy mt-3 leading-7 text-[var(--color-accent-strong)]">{warningMessage}</p>{/if}
	{#if errorMessage}<p class="readable-copy mt-3 leading-7 text-[var(--color-danger-text)]">{errorMessage}</p>{/if}
</section>
