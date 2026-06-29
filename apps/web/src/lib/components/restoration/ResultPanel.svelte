<script lang="ts">
	import type { JobMetadata } from '$lib/types';

	let {
		isProcessing,
		resultPreviewUrl,
		statusMessage,
		metadata
	}: {
		isProcessing: boolean;
		resultPreviewUrl: string | null;
		statusMessage: string;
		metadata: JobMetadata | null;
	} = $props();
</script>

<section class="panel result-panel" aria-labelledby="result-title">
	<div class="section-header">
		<p>Step 3</p>
		<h2 id="result-title">Result</h2>
	</div>

	{#if isProcessing}
		<div class="progress-card" aria-live="polite">
			<div class="progress-bar" aria-label="Processing progress"><span></span></div>
			<p>{statusMessage}</p>
		</div>
	{:else if resultPreviewUrl}
		<div class="preview-card result-preview">
			<img src={resultPreviewUrl} alt="Restored result preview" />
		</div>
		<a class="download-link" href={resultPreviewUrl} download="pixelreforge-result.png">Download PNG</a>
	{:else}
		<div class="empty-result">The restored image and metadata will appear here.</div>
	{/if}

	{#if metadata}
		<dl class="metadata">
			<div><dt>Status</dt><dd>{metadata.status}</dd></div>
			<div><dt>Source size</dt><dd>{metadata.source_size?.join(' x ') ?? 'unknown'}</dd></div>
			<div><dt>Target size</dt><dd>{metadata.target_size?.join(' x ') ?? 'unknown'}</dd></div>
			<div><dt>Scale</dt><dd>{metadata.scale_x ?? '?'}x / {metadata.scale_y ?? '?'}y</dd></div>
			<div><dt>Method</dt><dd>{metadata.scale_method ?? 'unknown'}</dd></div>
			<div><dt>Confidence</dt><dd>{metadata.confidence?.toFixed(3) ?? 'unknown'}</dd></div>
		</dl>
	{/if}
</section>
