<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import { Slider } from '$lib/components/ui/slider';
	import type { JobMetadata } from '$lib/types';
	import type { HelpText } from '$lib/ui/types';
	import HelpButton from './HelpButton.svelte';

	type PreviewMode = 'side-by-side' | 'slider';
	type PreviewPane = 'source' | 'result';

	let {
		isProcessing,
		sourcePreviewUrl,
		resultPreviewUrl,
		statusMessage,
		metadata
	}: {
		isProcessing: boolean;
		sourcePreviewUrl: string | null;
		resultPreviewUrl: string | null;
		statusMessage: string;
		metadata: JobMetadata | null;
	} = $props();

	let mode = $state<PreviewMode>('side-by-side');
	let split = $state(50);
	let zoom = $state(1);
	let sourceViewport = $state<HTMLDivElement | null>(null);
	let resultViewport = $state<HTMLDivElement | null>(null);
	let syncingScroll = false;
	let dragStart: { pane: PreviewPane; x: number; y: number; left: number; top: number } | null = null;

	const compareSize = $derived.by(() => {
		const source = metadata?.source_size;
		const target = metadata?.target_size;
		if (source) return { width: source[0], height: source[1] };
		if (target && metadata?.scale_x && metadata?.scale_y) {
			return {
				width: Math.round(target[0] * metadata.scale_x),
				height: Math.round(target[1] * metadata.scale_y)
			};
		}
		return { width: 720, height: 480 };
	});
	const compareStyle = $derived(`width: ${compareSize.width * zoom}px; height: ${compareSize.height * zoom}px;`);

	const metadataHelp: Record<string, HelpText> = {
		source: {
			id: 'metadata-source-size-help',
			label: 'Source size',
			description: 'Pixel dimensions of the uploaded image before restoration.'
		},
		result: {
			id: 'metadata-result-size-help',
			label: 'Result size',
			description: 'Pixel dimensions of the restored output after the detected scale is removed.'
		},
		scale: {
			id: 'metadata-scale-help',
			label: 'Scale',
			description: 'Detected horizontal and vertical enlargement factors used to restore the original size.'
		},
		method: {
			id: 'metadata-method-help',
			label: 'Method',
			description: 'Algorithm path used for the scale detection or restoration step.'
		},
		confidence: {
			id: 'metadata-confidence-help',
			label: 'Confidence',
			description: 'How certain the detector is about the selected scale. Higher values mean a more reliable match.'
		}
	};

	function controlVariant(active: boolean) {
		return active ? 'primary' : 'secondary';
	}

	function syncScroll(from: PreviewPane) {
		if (syncingScroll) return;
		const source = from === 'source' ? sourceViewport : resultViewport;
		const target = from === 'source' ? resultViewport : sourceViewport;
		if (!source || !target) return;

		syncingScroll = true;
		target.scrollLeft = source.scrollLeft;
		target.scrollTop = source.scrollTop;
		requestAnimationFrame(() => {
			syncingScroll = false;
		});
	}

	function startPan(event: PointerEvent, pane: PreviewPane) {
		const viewport = pane === 'source' ? sourceViewport : resultViewport;
		if (!viewport) return;
		dragStart = { pane, x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
		viewport.setPointerCapture(event.pointerId);
	}

	function pan(event: PointerEvent) {
		if (!dragStart) return;
		const viewport = dragStart.pane === 'source' ? sourceViewport : resultViewport;
		if (!viewport) return;
		viewport.scrollLeft = dragStart.left - (event.clientX - dragStart.x);
		viewport.scrollTop = dragStart.top - (event.clientY - dragStart.y);
		syncScroll(dragStart.pane);
	}

	function stopPan() {
		dragStart = null;
	}
</script>

<section class="rounded-[1.75rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-panel)] backdrop-blur md:p-7" aria-labelledby="result-title">
	<div class="mb-5 flex items-end justify-between gap-4">
		<p class="text-xl uppercase tracking-[0.18em] text-[var(--color-accent)]">Step 3</p>
		<h2 id="result-title" class="text-4xl">Result</h2>
	</div>

	{#if isProcessing}
		<div class="grid min-h-56 place-items-center gap-4 rounded-[1.25rem] border border-[var(--color-border)] bg-[var(--color-surface-soft)] text-center text-[var(--color-text-muted)]" aria-live="polite">
			<div class="h-3 w-full max-w-lg overflow-hidden rounded-full bg-[rgba(251,242,223,0.12)]" aria-label="Processing progress">
				<span class="block h-full w-2/5 rounded-full bg-[linear-gradient(90deg,var(--color-action),var(--color-accent-strong),var(--color-action))] [animation:progress-sweep_1.2s_infinite_ease-in-out]"></span>
			</div>
			<p class="readable-copy">{statusMessage}</p>
		</div>
	{:else if resultPreviewUrl}
		<div class="mb-4 flex flex-col gap-3 rounded-[1.25rem] bg-[var(--color-surface-soft)] p-4 md:flex-row md:items-end md:justify-between">
			<div class="flex flex-wrap gap-2">
				<Button variant={controlVariant(mode === 'side-by-side')} type="button" onclick={() => (mode = 'side-by-side')}>Side by side</Button>
				<Button variant={controlVariant(mode === 'slider')} type="button" onclick={() => (mode = 'slider')} disabled={!sourcePreviewUrl}>Slider</Button>
			</div>
			<div class="grid min-w-48 gap-1">
				<label class="readable-copy text-sm text-[var(--color-text-muted)]" for="zoom-range">Zoom {zoom.toFixed(1)}x</label>
				<Slider id="zoom-range" min={1} max={4} step={0.25} bind:value={zoom} />
			</div>
		</div>

		{#if mode === 'slider' && sourcePreviewUrl}
			<div class="mb-4 grid gap-2">
				<label class="readable-copy text-sm text-[var(--color-text-muted)]" for="split-range">Before / after split {split}%</label>
				<Slider id="split-range" min={0} max={100} step={1} bind:value={split} />
			</div>
			<figure>
				<div class="pixel-preview relative grid h-[min(68vh,42rem)] min-h-96 place-items-center overflow-auto rounded-[1.25rem] p-4">
					<div class="relative max-w-none" style={compareStyle}>
						<img class="pixelated absolute inset-0 size-full object-fill" src={resultPreviewUrl} alt="Restored result preview" />
						<div class="absolute inset-0 overflow-hidden" style={`clip-path: inset(0 ${100 - split}% 0 0);`} aria-hidden="true">
							<img class="pixelated size-full object-fill" src={sourcePreviewUrl} alt="" />
						</div>
					</div>
				</div>
				<figcaption class="readable-copy mt-2 flex justify-between text-sm text-[var(--color-text-muted)]">
					<span>Before</span>
					<span>After</span>
				</figcaption>
			</figure>
		{:else}
			<div class="grid gap-4 lg:grid-cols-2">
				{#if sourcePreviewUrl}
					<figure>
						<div
							class="pixel-preview grid h-[min(68vh,42rem)] min-h-96 cursor-grab place-items-center overflow-auto rounded-[1.25rem] p-4 active:cursor-grabbing"
							role="presentation"
							bind:this={sourceViewport}
							onscroll={() => syncScroll('source')}
							onpointerdown={(event) => startPan(event, 'source')}
							onpointermove={pan}
							onpointerup={stopPan}
							onpointercancel={stopPan}
						>
							<img class="pixelated max-w-none object-fill" style={compareStyle} src={sourcePreviewUrl} alt="Selected source preview" draggable="false" />
						</div>
						<figcaption class="readable-copy mt-2 text-center text-sm text-[var(--color-text-muted)]">Before</figcaption>
					</figure>
				{/if}
				<figure>
					<div
						class="pixel-preview grid h-[min(68vh,42rem)] min-h-96 cursor-grab place-items-center overflow-auto rounded-[1.25rem] p-4 active:cursor-grabbing"
						role="presentation"
						bind:this={resultViewport}
						onscroll={() => syncScroll('result')}
						onpointerdown={(event) => startPan(event, 'result')}
						onpointermove={pan}
						onpointerup={stopPan}
						onpointercancel={stopPan}
					>
						<img class="pixelated max-w-none object-fill" style={compareStyle} src={resultPreviewUrl} alt="Restored result preview" draggable="false" />
					</div>
					<figcaption class="readable-copy mt-2 text-center text-sm text-[var(--color-text-muted)]">After</figcaption>
				</figure>
			</div>
		{/if}

		<a class="mt-4 inline-flex min-h-13 w-full items-center justify-center rounded-2xl bg-[var(--color-accent)] px-5 text-2xl font-black tracking-[0.12em] text-[var(--color-bg-deep)] transition hover:-translate-y-0.5 hover:bg-[var(--color-accent-strong)]" href={resultPreviewUrl} download="pixelreforge-result.png">Download PNG</a>
	{:else}
		<div class="readable-copy grid min-h-56 place-items-center rounded-[1.25rem] border border-[var(--color-border)] bg-[var(--color-surface-soft)] p-6 text-center text-[var(--color-text-muted)]">
			The restored image and metadata will appear here.
		</div>
	{/if}

	{#if metadata}
		<dl class="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
			<div class="rounded-2xl bg-[var(--color-surface-soft)] p-3"><dt class="readable-copy text-xs font-normal normal-case leading-5 tracking-normal text-[var(--color-text-soft)]">Status</dt><dd class="mt-1 break-words text-[var(--color-text)]">{metadata.status}</dd></div>
			<div class="grid gap-3 rounded-2xl bg-[var(--color-surface-soft)] p-3 sm:row-span-2">
				<div><dt class="readable-copy flex items-center gap-2 text-xs font-normal normal-case leading-5 tracking-normal text-[var(--color-text-soft)]">Source size <HelpButton help={metadataHelp.source} /></dt><dd class="mt-1 break-words text-[var(--color-text)]">{metadata.source_size?.join(' x ') ?? 'unknown'}</dd></div>
				<div><dt class="readable-copy flex items-center gap-2 text-xs font-normal normal-case leading-5 tracking-normal text-[var(--color-text-soft)]">Result size <HelpButton help={metadataHelp.result} /></dt><dd class="mt-1 break-words text-[var(--color-text)]">{metadata.target_size?.join(' x ') ?? 'unknown'}</dd></div>
			</div>
			<div class="rounded-2xl bg-[var(--color-surface-soft)] p-3"><dt class="readable-copy flex items-center gap-2 text-xs font-normal normal-case leading-5 tracking-normal text-[var(--color-text-soft)]">Scale <HelpButton help={metadataHelp.scale} /></dt><dd class="mt-1 break-words text-[var(--color-text)]">{metadata.scale_x ?? '?'}x / {metadata.scale_y ?? '?'}y</dd></div>
			<div class="rounded-2xl bg-[var(--color-surface-soft)] p-3"><dt class="readable-copy flex items-center gap-2 text-xs font-normal normal-case leading-5 tracking-normal text-[var(--color-text-soft)]">Method <HelpButton help={metadataHelp.method} /></dt><dd class="mt-1 break-words text-[var(--color-text)]">{metadata.scale_method ?? 'unknown'}</dd></div>
			<div class="rounded-2xl bg-[var(--color-surface-soft)] p-3"><dt class="readable-copy flex items-center gap-2 text-xs font-normal normal-case leading-5 tracking-normal text-[var(--color-text-soft)]">Confidence <HelpButton help={metadataHelp.confidence} /></dt><dd class="mt-1 break-words text-[var(--color-text)]">{metadata.confidence?.toFixed(3) ?? 'unknown'}</dd></div>
		</dl>
	{/if}
</section>
