<script lang="ts">
	import { cancelJob, createJob, downloadResult, getJob } from '$lib/api';
	import type { JobMetadata, RestoreSettings, ScaleMode } from '$lib/types';

	type HelpText = {
		id: string;
		label: string;
		description: string;
		impact: string;
		example: string;
	};

	type NotificationTone = 'info' | 'warning' | 'error';

	type UiNotification = {
		id: number;
		tone: NotificationTone;
		title: string;
		message: string;
	};

	let selectedFile = $state<File | null>(null);
	let sourcePreviewUrl = $state<string | null>(null);
	let resultPreviewUrl = $state<string | null>(null);
	let resultBlob = $state<Blob | null>(null);
	let metadata = $state<JobMetadata | null>(null);
	let currentJobId = $state<string | null>(null);
	let scaleMode = $state<ScaleMode>('auto');
	let manualScale = $state(4);
	let minScale = $state(2);
	let maxScale = $state(16);
	let confidenceThreshold = $state(0.45);
	let originalWidth = $state<number | undefined>();
	let originalHeight = $state<number | undefined>();
	let statusMessage = $state('Drop a pixel art image to start.');
	let errorMessage = $state<string | null>(null);
	let warningMessage = $state<string | null>(null);
	let notifications = $state<UiNotification[]>([]);
	let isDragging = $state(false);
	let isProcessing = $state(false);
	let isCancelling = $state(false);
	let nextNotificationId = 1;

	const basicHelp: HelpText[] = [
		{
			id: 'scale-mode-help',
			label: 'Scale mode',
			description: 'Controls whether PixelReForge estimates the enlargement scale or uses your value.',
			impact: 'Auto is faster to try, manual is safer for noisy JPEG files or known scales.',
			example: 'Auto can detect a clean 3x image; manual 4x restores a known 500 x 500 input to 125 x 125.'
		},
		{
			id: 'manual-scale-help',
			label: 'Manual scale',
			description: 'The integer enlargement factor used by the current MVP algorithm.',
			impact: 'Higher values produce a smaller restored image. Wrong values can crush or duplicate details.',
			example: '4x turns 500 x 500 into 125 x 125. 2x turns 500 x 500 into 250 x 250.'
		}
	];

	const advancedHelp: HelpText[] = [
		{
			id: 'auto-range-help',
			label: 'Auto scale range',
			description: 'Limits the integer scale candidates tested by the MVP detector.',
			impact: 'A narrower range can avoid false positives when you already know the likely scale.',
			example: 'Use 2..6 for common web upscales; use 2..16 when the source may be tiny.'
		},
		{
			id: 'confidence-help',
			label: 'Confidence threshold',
			description: 'The minimum confidence before the result is treated as suspicious.',
			impact: 'Higher values create more warnings. Lower values let uncertain results pass quietly.',
			example: '0.45 warns on many JPEGs; 0.25 is more permissive for noisy images.'
		},
		{
			id: 'original-size-help',
			label: 'Original size override',
			description: 'Reserved for the next fractional-scale algorithm, where the restored size may not be input / integer scale.',
			impact: 'This will support cases like 1.5x, 2.5x, cropped inputs, and user-provided target dimensions.',
			example: 'A 300 x 300 image enlarged from 200 x 200 is 1.5x and needs this future mode.'
		}
	];

	function helpFor(id: string): HelpText {
		return [...basicHelp, ...advancedHelp].find((item) => item.id === id)!;
	}

	function handleFileInput(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		selectFile(input.files?.[0] ?? null);
	}

	function handleDrop(event: DragEvent) {
		event.preventDefault();
		isDragging = false;
		selectFile(event.dataTransfer?.files?.[0] ?? null);
	}

	function selectFile(file: File | null) {
		clearResult();
		clearNotifications();
		errorMessage = null;
		warningMessage = null;
		currentJobId = null;

		if (!file) {
			selectedFile = null;
			setSourcePreview(null);
			statusMessage = 'Drop a pixel art image to start.';
			return;
		}

		if (!file.type.startsWith('image/')) {
			selectedFile = null;
			setSourcePreview(null);
			errorMessage = 'Only image files are supported.';
			addNotification('error', 'Unsupported file', errorMessage);
			return;
		}

		selectedFile = file;
		setSourcePreview(URL.createObjectURL(file));
		statusMessage = 'Image ready. Review settings and start restoration.';

		if (isJpegFile(file)) {
			addNotification(
				'warning',
				'JPEG input detected',
				'JPEG compression can add noise to pixel art. Auto scale may still work, but review the result and warnings after processing.'
			);
		}
	}

	async function restoreImage() {
		if (!selectedFile || isProcessing) return;

		clearResult();
		errorMessage = null;
		warningMessage = null;
		isProcessing = true;
		isCancelling = false;
		statusMessage = 'Uploading image...';

		try {
			const created = await createJob(selectedFile, currentSettings());
			currentJobId = created.job_id;
			statusMessage = 'Processing image...';

			const completed = await waitForCompletion(created.job_id);
			metadata = completed;

			if (completed.status === 'cancelled') {
				statusMessage = 'Restoration cancelled.';
				return;
			}

			statusMessage = 'Downloading result...';
			resultBlob = await downloadResult(created.job_id);
			resultPreviewUrl = URL.createObjectURL(resultBlob);
			warningMessage = completed.warnings.join(' ') || null;
			if (warningMessage) {
				addNotification('warning', 'Restoration warning', warningMessage);
			}
			addNotification('info', 'Image ready', 'Restoration complete. You can preview and download the PNG result.');
			statusMessage = 'Restoration complete.';
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Unexpected processing error.';
			addNotification('error', 'Restoration failed', errorMessage);
			statusMessage = 'Restoration failed.';
		} finally {
			isProcessing = false;
			isCancelling = false;
		}
	}

	async function requestCancel() {
		if (!currentJobId || isCancelling) return;

		isCancelling = true;
		statusMessage = 'Cancelling job...';
		try {
			metadata = await cancelJob(currentJobId);
			statusMessage = metadata.status === 'cancelled' ? 'Restoration cancelled.' : `Job is already ${metadata.status}.`;
			addNotification('info', 'Processing stopped', statusMessage);
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Failed to cancel job.';
			addNotification('error', 'Cancel failed', errorMessage);
		} finally {
			isProcessing = false;
			isCancelling = false;
		}
	}

	async function waitForCompletion(jobId: string): Promise<JobMetadata> {
		for (let attempt = 0; attempt < 60; attempt += 1) {
			const job = await getJob(jobId);

			if (job.status === 'completed' || job.status === 'cancelled') return job;
			if (job.status === 'failed') {
				throw new Error(job.error ?? 'Processing job failed.');
			}

			statusMessage = `Processing image... ${job.status}`;
			await new Promise((resolve) => setTimeout(resolve, 500));
		}

		throw new Error('Processing timed out.');
	}

	function currentSettings(): RestoreSettings {
		return {
			scaleMode,
			manualScale,
			minScale,
			maxScale,
			confidenceThreshold
		};
	}

	function clearResult() {
		metadata = null;
		resultBlob = null;
		if (resultPreviewUrl) URL.revokeObjectURL(resultPreviewUrl);
		resultPreviewUrl = null;
	}

	function setSourcePreview(url: string | null) {
		if (sourcePreviewUrl) URL.revokeObjectURL(sourcePreviewUrl);
		sourcePreviewUrl = url;
	}

	function isJpegFile(file: File): boolean {
		const fileName = file.name.toLowerCase();
		return file.type === 'image/jpeg' || fileName.endsWith('.jpg') || fileName.endsWith('.jpeg');
	}

	function addNotification(tone: NotificationTone, title: string, message: string) {
		notifications = [
			...notifications,
			{
				id: nextNotificationId,
				tone,
				title,
				message
			}
		];
		nextNotificationId += 1;
	}

	function dismissNotification(id: number) {
		notifications = notifications.filter((notification) => notification.id !== id);
	}

	function clearNotifications() {
		notifications = [];
	}
</script>

<svelte:head>
	<title>PixelReForge MVP</title>
	<meta name="description" content="Restore pixel art to its original form." />
</svelte:head>

<main class="shell">
	<section class="hero">
		<p class="eyebrow">PixelReForge MVP</p>
		<h1>Restore pixel art to its original form.</h1>
		<p class="lead">
			Upload an enlarged pixel art image, choose how scale should be detected, and download a restored PNG.
		</p>
	</section>

	<section class="flow" aria-label="Image restoration workflow">
		<section class="panel upload-panel" aria-labelledby="upload-title">
			<div class="section-header">
				<p>Step 1</p>
				<h2 id="upload-title">Upload image</h2>
			</div>

			<div
				class:dragging={isDragging}
				class="dropzone"
				ondragover={(event) => {
					event.preventDefault();
					isDragging = true;
				}}
				ondragleave={() => (isDragging = false)}
				ondrop={handleDrop}
				role="button"
				tabindex="0"
			>
				<strong>Drop image here</strong>
				<span>PNG, JPEG, GIF, or WebP input</span>
				<input accept="image/*" type="file" onchange={handleFileInput} />
			</div>

			{#if selectedFile}
				<p class="file-line">Selected: {selectedFile.name} ({Math.round(selectedFile.size / 1024)} KB)</p>
			{/if}

			{#if sourcePreviewUrl}
				<div class="preview-card source-preview">
					<img src={sourcePreviewUrl} alt="Selected source preview" />
				</div>
			{/if}
		</section>

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
						{@render HelpButton({ help: helpFor('scale-mode-help') })}
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
							{@render HelpButton({ help: helpFor('manual-scale-help') })}
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
							{@render HelpButton({ help: helpFor('auto-range-help') })}
						</div>
						<input type="number" min="1" max={maxScale} bind:value={minScale} disabled={isProcessing} />
					</label>
					<label class="field-block">
						<div class="field-heading">
							<span>Max scale</span>
							{@render HelpButton({ help: helpFor('auto-range-help') })}
						</div>
						<input type="number" min={minScale} max="64" bind:value={maxScale} disabled={isProcessing} />
					</label>
				</div>

				<label class="field-block">
					<div class="field-heading">
						<span>Confidence threshold</span>
						{@render HelpButton({ help: helpFor('confidence-help') })}
					</div>
					<input
						type="range"
						min="0"
						max="1"
						step="0.05"
						bind:value={confidenceThreshold}
						disabled={isProcessing}
					/>
					<strong class="value-readout">{confidenceThreshold.toFixed(2)}</strong>
				</label>

				<div class="field-grid muted-grid" aria-label="Original size override planned for next algorithm">
					<label class="field-block">
						<div class="field-heading">
							<span>Original width</span>
							{@render HelpButton({ help: helpFor('original-size-help') })}
						</div>
						<input type="number" min="1" bind:value={originalWidth} disabled placeholder="v2" />
					</label>
					<label class="field-block">
						<div class="field-heading">
							<span>Original height</span>
							{@render HelpButton({ help: helpFor('original-size-help') })}
						</div>
						<input type="number" min="1" bind:value={originalHeight} disabled placeholder="v2" />
					</label>
				</div>
			</details>

			<div class="actions">
				<button class="restore-button" disabled={!selectedFile || isProcessing} onclick={restoreImage}>
					{isProcessing ? 'Restoring...' : 'Restore image'}
				</button>
				{#if isProcessing}
					<button class="cancel-button" disabled={isCancelling} onclick={requestCancel}>
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
	</section>
</main>

{#if notifications.length > 0}
	<section class="notification-stack" aria-label="Interface messages" aria-live="polite">
		{#each notifications as notification (notification.id)}
			<article class={`notification ${notification.tone}`}>
				<div>
					<strong>{notification.title}</strong>
					<p>{notification.message}</p>
				</div>
				<button type="button" aria-label="Dismiss notification" onclick={() => dismissNotification(notification.id)}>
					Close
				</button>
			</article>
		{/each}
	</section>
{/if}

{#snippet HelpButton({ help }: { help: HelpText })}
	<span class="help-wrap">
		<button class="help-button" type="button" aria-describedby={help.id}>?</button>
		<span class="tooltip" id={help.id} role="tooltip">
			<strong>{help.label}</strong>
			<span>{help.description}</span>
			<span>Impact: {help.impact}</span>
			<span>Example: {help.example}</span>
		</span>
	</span>
{/snippet}

<style>
	:global(body) {
		margin: 0;
		font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
		background: #0c0d13;
		color: #f4efe7;
	}

	:global(*) { box-sizing: border-box; }

	.shell {
		min-height: 100vh;
		padding: 36px clamp(16px, 4vw, 56px) 56px;
		background:
			radial-gradient(circle at 15% 5%, rgba(189, 215, 133, 0.18), transparent 30rem),
			radial-gradient(circle at 85% 0%, rgba(115, 83, 183, 0.18), transparent 26rem),
			linear-gradient(145deg, #0c0d13 0%, #151421 52%, #0d0e14 100%);
	}

	.hero, .flow { max-width: 1040px; margin: 0 auto; }
	.hero { margin-bottom: 28px; }
	.eyebrow { margin: 0 0 12px; color: #bdd785; font-size: 0.78rem; font-weight: 800; letter-spacing: 0.18em; text-transform: uppercase; }
	h1 { max-width: 820px; margin: 0; font-size: clamp(2.6rem, 7vw, 5.8rem); line-height: 0.9; letter-spacing: -0.07em; }
	.lead { max-width: 720px; margin: 20px 0 0; color: #c9c1b3; font-size: clamp(1rem, 2vw, 1.18rem); line-height: 1.6; }

	.flow { display: grid; gap: 18px; }
	.panel { border: 1px solid rgba(244, 239, 231, 0.13); border-radius: 28px; padding: clamp(18px, 3vw, 28px); background: rgba(14, 15, 24, 0.82); box-shadow: 0 28px 90px rgba(0, 0, 0, 0.32); backdrop-filter: blur(18px); }
	.section-header { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
	.section-header p { margin: 0; color: #bdd785; font-size: 0.76rem; font-weight: 900; letter-spacing: 0.18em; text-transform: uppercase; }
	h2 { margin: 0; font-size: clamp(1.45rem, 4vw, 2.2rem); letter-spacing: -0.04em; }
	h3 { margin: 0 0 14px; color: #f4efe7; font-size: 0.92rem; letter-spacing: 0.12em; text-transform: uppercase; }

	.dropzone { display: grid; gap: 8px; place-items: center; min-height: 210px; border: 2px dashed rgba(189, 215, 133, 0.42); border-radius: 22px; padding: 22px; background: rgba(189, 215, 133, 0.06); color: #ece7de; text-align: center; transition: border-color 160ms ease, background 160ms ease, transform 160ms ease; }
	.dropzone.dragging { border-color: #bdd785; background: rgba(189, 215, 133, 0.16); transform: translateY(-2px); }
	.dropzone strong { font-size: 1.35rem; }
	.dropzone span, .file-line, .status, .notice, .empty-result, .progress-card, .warning { color: #c9c1b3; }
	.dropzone input { max-width: 100%; color: #f4efe7; }
	.file-line { margin: 14px 0 0; font-size: 0.92rem; word-break: break-word; }

	.preview-card { display: grid; place-items: center; margin-top: 16px; min-height: 280px; border-radius: 20px; background: linear-gradient(45deg, rgba(255, 255, 255, 0.05) 25%, transparent 25%), linear-gradient(-45deg, rgba(255, 255, 255, 0.05) 25%, transparent 25%), #10121b; background-size: 24px 24px; overflow: hidden; }
	.preview-card img { max-width: 100%; max-height: 520px; image-rendering: pixelated; object-fit: contain; }

	.settings-group { display: grid; gap: 16px; padding: 18px; border-radius: 22px; background: rgba(255, 255, 255, 0.045); }
	.advanced-group { margin-top: 16px; }
	.advanced-group summary { cursor: pointer; color: #f4efe7; font-weight: 900; letter-spacing: 0.12em; text-transform: uppercase; }
	.advanced-group[open] summary { margin-bottom: 16px; }
	.field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
	.field-block { display: grid; gap: 10px; min-width: 0; }
	.field-heading { display: flex; align-items: center; gap: 8px; color: #f4efe7; font-weight: 800; }
	input[type='range'] { width: 100%; accent-color: #bdd785; }
	input[type='number'] { width: 100%; min-height: 44px; border: 1px solid rgba(244, 239, 231, 0.14); border-radius: 14px; padding: 0 12px; background: rgba(9, 10, 16, 0.78); color: #f4efe7; font: inherit; }
	input:disabled { opacity: 0.55; }
	.value-readout { color: #bdd785; font-size: 1.45rem; }
	.muted-grid { opacity: 0.82; }

	.segmented { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
	.segmented label { display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 48px; border: 1px solid rgba(244, 239, 231, 0.14); border-radius: 16px; background: rgba(9, 10, 16, 0.58); color: #c9c1b3; font-weight: 800; cursor: pointer; }
	.segmented label.active { border-color: rgba(189, 215, 133, 0.65); background: rgba(189, 215, 133, 0.12); color: #f4efe7; }
	.segmented input { accent-color: #bdd785; }
	.notice { margin: 0; line-height: 1.55; }

	.help-wrap { position: relative; display: inline-flex; }
	.help-button { display: inline-grid; place-items: center; width: 22px; height: 22px; border: 1px solid rgba(189, 215, 133, 0.58); border-radius: 999px; background: rgba(189, 215, 133, 0.08); color: #bdd785; font: inherit; font-size: 0.78rem; font-weight: 900; cursor: help; }
	.tooltip { position: absolute; z-index: 5; top: calc(100% + 10px); left: 50%; display: none; width: min(320px, 78vw); transform: translateX(-50%); gap: 8px; padding: 14px; border: 1px solid rgba(244, 239, 231, 0.14); border-radius: 16px; background: #11131d; color: #d9d2c7; box-shadow: 0 18px 50px rgba(0, 0, 0, 0.45); font-size: 0.86rem; line-height: 1.45; }
	.tooltip strong { color: #f4efe7; }
	.help-wrap:hover .tooltip, .help-button:focus + .tooltip { display: grid; }

	.actions { display: flex; gap: 12px; margin-top: 18px; }
	.restore-button, .cancel-button, .download-link { display: inline-flex; align-items: center; justify-content: center; min-height: 50px; border: 0; border-radius: 16px; font: inherit; font-weight: 900; text-decoration: none; cursor: pointer; }
	.restore-button, .download-link { flex: 1; background: #bdd785; color: #171720; }
	.cancel-button { padding: 0 20px; background: rgba(255, 111, 111, 0.13); color: #ffb4b4; border: 1px solid rgba(255, 111, 111, 0.28); }
	.restore-button:disabled, .cancel-button:disabled { cursor: not-allowed; opacity: 0.55; }
	.status, .warning, .error { margin: 14px 0 0; line-height: 1.5; }
	.warning { color: #ffd88a; }
	.error { color: #ff9c9c; }
	.notification-stack { position: fixed; z-index: 20; right: clamp(14px, 3vw, 30px); bottom: clamp(14px, 3vw, 30px); display: grid; gap: 12px; width: min(420px, calc(100vw - 28px)); }
	.notification { display: flex; align-items: start; justify-content: space-between; gap: 14px; padding: 14px; border: 1px solid rgba(244, 239, 231, 0.14); border-left-width: 5px; border-radius: 18px; background: rgba(17, 19, 29, 0.96); box-shadow: 0 18px 55px rgba(0, 0, 0, 0.42); backdrop-filter: blur(18px); }
	.notification.info { border-left-color: #bdd785; }
	.notification.warning { border-left-color: #ffd88a; }
	.notification.error { border-left-color: #ff9c9c; }
	.notification strong { display: block; color: #f4efe7; }
	.notification p { margin: 5px 0 0; color: #c9c1b3; line-height: 1.45; }
	.notification button { flex: 0 0 auto; border: 1px solid rgba(244, 239, 231, 0.16); border-radius: 999px; padding: 7px 10px; background: rgba(255, 255, 255, 0.06); color: #f4efe7; font: inherit; font-size: 0.78rem; font-weight: 900; cursor: pointer; }

	.progress-card, .empty-result { display: grid; place-items: center; gap: 16px; min-height: 220px; border: 1px solid rgba(244, 239, 231, 0.1); border-radius: 20px; background: rgba(255, 255, 255, 0.04); text-align: center; }
	.progress-bar { width: min(520px, 100%); height: 12px; overflow: hidden; border-radius: 999px; background: rgba(244, 239, 231, 0.1); }
	.progress-bar span { display: block; width: 42%; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #bdd785, #f4efe7, #bdd785); animation: progress-sweep 1.2s infinite ease-in-out; }
	@keyframes progress-sweep { 0% { transform: translateX(-120%); } 100% { transform: translateX(260%); } }
	.download-link { width: 100%; margin-top: 16px; }
	.metadata { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 18px 0 0; }
	.metadata div { padding: 12px; border-radius: 14px; background: rgba(255, 255, 255, 0.05); }
	dt { color: #9d958a; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; }
	dd { margin: 6px 0 0; color: #f4efe7; font-weight: 800; word-break: break-word; }

	@media (max-width: 720px) {
		.shell { padding-top: 24px; }
		.section-header, .actions { align-items: stretch; flex-direction: column; }
		.field-grid, .segmented, .metadata { grid-template-columns: 1fr; }
		.notification-stack { right: 14px; bottom: 14px; }
		.notification { flex-direction: column; }
		h1 { font-size: clamp(2.35rem, 15vw, 4.2rem); }
	}
</style>
