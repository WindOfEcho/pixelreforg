<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import { buttonClass } from '$lib/components/ui/button/button.styles';
	import { Slider } from '$lib/components/ui/slider';
	import type { JobMetadata } from '$lib/types';

	let {
		isProcessing,
		atlasPreviewUrl,
		statusMessage,
		metadata,
		onDownloadMetadata
	}: {
		isProcessing: boolean;
		atlasPreviewUrl: string | null;
		statusMessage: string;
		metadata: JobMetadata | null;
		onDownloadMetadata: () => void;
	} = $props();

	let zoom = $state(1);
	let showPixelGrid = $state(false);
	let viewport = $state<HTMLDivElement | null>(null);
	let viewportWidth = $state(0);
	let viewportHeight = $state(0);
	let dragStart = $state<{ x: number; y: number; left: number; top: number } | null>(null);

	const atlasSize = $derived(metadata?.target_size ? { width: metadata.target_size[0], height: metadata.target_size[1] } : { width: 512, height: 512 });
	const fitScale = $derived.by(() => {
		const availableWidth = Math.max(1, viewportWidth - 32);
		const availableHeight = Math.max(1, viewportHeight - 32);
		return Math.min(1, availableWidth / atlasSize.width, availableHeight / atlasSize.height);
	});
	const displayScale = $derived(fitScale * zoom);
	const atlasStyle = $derived(`width: ${atlasSize.width * displayScale}px; height: ${atlasSize.height * displayScale}px;`);
	const gridStyle = $derived(
		`background-image: linear-gradient(to right, rgba(248,221,164,0.32) 1px, transparent 1px), linear-gradient(to bottom, rgba(248,221,164,0.32) 1px, transparent 1px); background-size: ${displayScale}px ${displayScale}px;`
	);
	const progressPercent = $derived(Math.max(0, Math.min(100, metadata?.progress_percent ?? 0)));
	const progressStyle = $derived(`width: ${progressPercent}%;`);
	const frameCount = $derived(typeof metadata?.analysis?.frame_count === 'number' ? metadata.analysis.frame_count : null);
	const packingMode = $derived(typeof metadata?.analysis?.packing_mode === 'string' ? metadata.analysis.packing_mode : null);
	const metadataAvailable = $derived(metadata?.analysis?.metadata_available === true);
	const downloadFilename = $derived.by(() => {
		const sourceName = metadata?.input_filename.replace(/\.[^.]+$/, '') ?? 'pixelreforge';
		const safeName = sourceName
			.replace(/[<>:"/\\|?*\u0000-\u001f]+/g, '-')
			.replace(/\s+/g, '-')
			.replace(/^-+|-+$/g, '');
		return `${safeName || 'pixelreforge'}-atlas.png`;
	});

	function startPan(event: PointerEvent) {
		if (event.button !== 0 || !viewport) return;
		event.preventDefault();
		dragStart = { x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
		viewport.setPointerCapture(event.pointerId);
	}

	function pan(event: PointerEvent) {
		if (!dragStart || !viewport) return;
		event.preventDefault();
		viewport.scrollLeft = dragStart.left - (event.clientX - dragStart.x);
		viewport.scrollTop = dragStart.top - (event.clientY - dragStart.y);
	}

	function stopPan() {
		dragStart = null;
	}

	function scrollPageFromPreview(event: WheelEvent) {
		if (event.ctrlKey) return;
		const unit = event.deltaMode === WheelEvent.DOM_DELTA_LINE ? 16 : event.deltaMode === WheelEvent.DOM_DELTA_PAGE ? window.innerHeight : 1;
		event.preventDefault();
		window.scrollBy({ left: event.deltaX * unit, top: event.deltaY * unit, behavior: 'auto' });
	}

	function changeZoom(delta: number) {
		zoom = Math.max(0.25, Math.min(8, Number((zoom + delta).toFixed(2))));
	}
</script>

<section class="min-w-0 rounded-[1.75rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-panel)] backdrop-blur md:p-7" aria-labelledby="atlas-result-title">
	<div class="mb-5 flex items-end justify-between gap-4">
		<p class="text-xl uppercase tracking-[0.18em] text-[var(--color-accent)]">Step 3</p>
		<h2 id="atlas-result-title" class="text-4xl">Atlas preview</h2>
	</div>

	{#if isProcessing}
		<div class="grid min-h-56 place-items-center gap-4 rounded-[1.25rem] border border-[var(--color-border)] bg-[var(--color-surface-soft)] p-6 text-center text-[var(--color-text-muted)]" aria-live="polite">
			<div class="h-3 w-full max-w-lg overflow-hidden rounded-full bg-[rgba(251,242,223,0.12)]" role="progressbar" aria-label="Atlas packing progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(progressPercent)}>
				<span class="block h-full rounded-full bg-[linear-gradient(90deg,var(--color-action),var(--color-accent-strong))] transition-[width] duration-300 ease-out" style={progressStyle}></span>
			</div>
			<p class="readable-copy">{statusMessage} ({Math.round(progressPercent)}%)</p>
		</div>
	{:else if atlasPreviewUrl}
		<div class="mb-4 flex flex-col gap-3 rounded-[1.25rem] bg-[var(--color-surface-soft)] p-4 lg:flex-row lg:items-end lg:justify-between">
			<div class="flex flex-wrap gap-2">
				<Button type="button" variant="secondary" onclick={() => changeZoom(-0.25)} disabled={zoom <= 0.25}>Zoom out</Button>
				<Button type="button" variant="secondary" onclick={() => changeZoom(0.25)} disabled={zoom >= 8}>Zoom in</Button>
				<label class="readable-copy flex items-center gap-2 rounded-2xl bg-[rgba(47,38,48,0.42)] px-3 text-sm text-[var(--color-text)]"><input type="checkbox" bind:checked={showPixelGrid} /> Pixel grid</label>
			</div>
			<div class="grid min-w-48 gap-1">
				<label class="readable-copy text-sm text-[var(--color-text-muted)]" for="atlas-zoom-range">Zoom {zoom.toFixed(2)}x</label>
				<Slider id="atlas-zoom-range" min={0.25} max={8} step={0.25} bind:value={zoom} />
			</div>
		</div>

		<figure class="min-w-0">
			<div
				class="pixel-preview grid h-[min(68vh,42rem)] min-h-96 w-full max-w-full min-w-0 cursor-grab place-items-center overflow-auto rounded-[1.25rem] p-4 active:cursor-grabbing"
				role="presentation"
				bind:this={viewport}
				bind:clientWidth={viewportWidth}
				bind:clientHeight={viewportHeight}
				onwheel={scrollPageFromPreview}
				onpointerdown={startPan}
				onpointermove={pan}
				onpointerup={stopPan}
				onpointercancel={stopPan}
			>
				<div class="relative max-w-none shrink-0" style={atlasStyle}>
					<img class="pixelated absolute inset-0 size-full object-fill" src={atlasPreviewUrl} alt="Generated sprite atlas preview" draggable="false" />
					{#if showPixelGrid && displayScale >= 3}<div class="pointer-events-none absolute inset-0" style={gridStyle} aria-hidden="true"></div>{/if}
				</div>
			</div>
			<figcaption class="readable-copy mt-2 flex flex-wrap justify-between gap-2 text-sm text-[var(--color-text-muted)]">
				<span>Drag to pan. Use controls to inspect individual pixels.</span>
				<span>{atlasSize.width} x {atlasSize.height} px</span>
			</figcaption>
		</figure>

		<div class="mt-4 grid gap-3 sm:grid-cols-2">
			<a href={atlasPreviewUrl} download={downloadFilename} class={buttonClass('primary', 'lg', 'w-full')}>Download PNG</a>
			{#if metadataAvailable}<Button size="lg" variant="secondary" class="w-full" onclick={onDownloadMetadata}>Download JSON metadata</Button>{/if}
		</div>
	{:else}
		<div class="readable-copy grid min-h-56 place-items-center rounded-[1.25rem] border border-[var(--color-border)] bg-[var(--color-surface-soft)] p-6 text-center text-[var(--color-text-muted)]">
			The generated atlas will appear here with zoom, pan, and download controls.
		</div>
	{/if}

	{#if metadata}
		<dl class="readable-copy mt-4 grid grid-cols-1 gap-2 rounded-[1.25rem] bg-[var(--color-surface-soft)] p-4 text-sm text-[var(--color-text-muted)] sm:grid-cols-2 lg:grid-cols-4">
			<div><dt class="text-[var(--color-text-soft)]">Status</dt><dd class="m-0 mt-1 text-[var(--color-text)]">{metadata.status}</dd></div>
			<div><dt class="text-[var(--color-text-soft)]">Frames</dt><dd class="m-0 mt-1 text-[var(--color-text)]">{frameCount ?? 'unknown'}</dd></div>
			<div><dt class="text-[var(--color-text-soft)]">Placement</dt><dd class="m-0 mt-1 text-[var(--color-text)]">{packingMode ?? 'unknown'}</dd></div>
			<div><dt class="text-[var(--color-text-soft)]">Input images</dt><dd class="m-0 mt-1 text-[var(--color-text)]">{metadata.input_filenames.length}</dd></div>
		</dl>
	{/if}
</section>
