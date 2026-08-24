<script lang="ts">
	import { SvelteMap } from 'svelte/reactivity';
	import { cancelSpriteSheetJob, createSpriteSheetJob, downloadSpriteSheet, downloadSpriteSheetMetadata, getSpriteSheetJob } from '$lib/api';
	import NotificationStack from '$lib/components/restoration/NotificationStack.svelte';
	import { SUPPORTED_IMAGE_ACCEPT } from '$lib/components/restoration/UploadPanel.svelte';
	import AtlasResultPanel from '$lib/components/spritesheet/AtlasResultPanel.svelte';
	import AtlasSettingsPanel from '$lib/components/spritesheet/AtlasSettingsPanel.svelte';
	import SpriteUploadPanel from '$lib/components/spritesheet/SpriteUploadPanel.svelte';
	import type { JobMetadata, SpriteSheetInputMode, SpriteSheetSettings } from '$lib/types';
	import { logUiError, userErrorMessage } from '$lib/ui/errors';
	import type { NotificationTone, UiNotification } from '$lib/ui/types';

	const JOB_POLL_INTERVAL_MS = 500;
	const JOB_TIMEOUT_MS = 1_800_000;
	const NOTIFICATION_AUTO_DISMISS_MS = 6000;

	let inputMode = $state<SpriteSheetInputMode>('files');
	let selectedFiles = $state<File[]>([]);
	let sourcePreviewUrl = $state<string | null>(null);
	let resultPreviewUrl = $state<string | null>(null);
	let metadata = $state<JobMetadata | null>(null);
	let currentJobId = $state<string | null>(null);
	let isDragging = $state(false);
	let isProcessing = $state(false);
	let isCancelling = $state(false);
	let statusMessage = $state('Choose individual sprites or a sheet to begin.');
	let errorMessage = $state<string | null>(null);
	let warningMessage = $state<string | null>(null);
	let notifications = $state<UiNotification[]>([]);
	let nextNotificationId = 1;
	let activeRun = 0;
	const notificationTimers = new SvelteMap<number, number>();
	let settings = $state<SpriteSheetSettings>({
		packingMode: 'compact',
		trimTransparent: true,
		alphaThreshold: 0,
		padding: 1,
		borderPadding: 0,
		extrude: 0,
		maxWidth: 2048,
		maxHeight: 2048,
		powerOfTwo: false,
		forceSquare: false,
		allowRotation: false,
		sortMode: 'area',
		backgroundColor: null,
		includeMetadata: true,
		extractionMode: 'auto',
		offsetX: 0,
		offsetY: 0,
		gapX: 0,
		gapY: 0
	});

	function changeInputMode(mode: SpriteSheetInputMode) {
		if (isProcessing) return;
		if (mode === inputMode) return;
		inputMode = mode;
		selectFiles([]);
		statusMessage = mode === 'files' ? 'Choose the individual sprites to pack.' : 'Choose one source sheet to split and repack.';
	}

	function selectFiles(files: File[]) {
		if (isProcessing) return;
		activeRun += 1;
		clearResult();
		clearNotifications();
		errorMessage = null;
		warningMessage = null;
		currentJobId = null;

		if (files.length === 0) {
			selectedFiles = [];
			setSourcePreview(null);
			statusMessage = inputMode === 'files' ? 'Choose individual sprites to pack.' : 'Choose one source sheet to split and repack.';
			return;
		}
		if (inputMode === 'sheet' && files.length !== 1) {
			selectedFiles = [];
			setSourcePreview(null);
			errorMessage = 'Sheet mode accepts exactly one image. Switch to separate files to pack a series.';
			addNotification('error', 'Choose one sheet', errorMessage);
			return;
		}
		const unsupported = files.find((file) => !isSupportedImage(file));
		if (unsupported) {
			selectedFiles = [];
			setSourcePreview(null);
			errorMessage = 'Only PNG, JPEG, GIF, and WebP images are supported.';
			addNotification('error', 'Unsupported file', errorMessage);
			return;
		}

		selectedFiles = files;
		setSourcePreview(URL.createObjectURL(files[0]));
		statusMessage = inputMode === 'files' ? `${files.length} ${files.length === 1 ? 'sprite is' : 'sprites are'} ready to pack.` : 'Sheet ready. Choose extraction and packing settings.';
		if (files.some(isJpegFile)) {
			warningMessage = 'JPEG has no alpha channel and can introduce compression artifacts. PNG is recommended for pixel art.';
			addNotification('warning', 'JPEG input detected', warningMessage);
		}
	}

	function removeFile(index: number) {
		if (isProcessing) return;
		selectFiles(selectedFiles.filter((_, candidateIndex) => candidateIndex !== index));
	}

	async function createAtlas() {
		if (selectedFiles.length === 0 || isProcessing) return;
		if (inputMode === 'sheet' && settings.extractionMode === 'grid' && (!settings.cellWidth || !settings.cellHeight)) {
			errorMessage = 'Manual sheet extraction needs both a cell width and cell height.';
			addNotification('error', 'Missing grid size', errorMessage);
			return;
		}
		if ((settings.atlasWidth === undefined) !== (settings.atlasHeight === undefined)) {
			errorMessage = 'Set both fixed atlas dimensions or leave both blank for automatic sizing.';
			addNotification('error', 'Incomplete atlas size', errorMessage);
			return;
		}

		clearResult();
		errorMessage = null;
		warningMessage = null;
		isProcessing = true;
		isCancelling = false;
		statusMessage = 'Uploading sprite images...';
		const runId = activeRun + 1;
		activeRun = runId;

		try {
			const created = await createSpriteSheetJob(selectedFiles, inputMode, settings);
			if (runId !== activeRun) return;
			currentJobId = created.job_id;
			statusMessage = 'Packing sprite atlas...';
			const completed = await waitForCompletion(created.job_id, runId);
			if (completed === null || runId !== activeRun) return;
			metadata = completed;
			if (completed.status === 'cancelled') {
				statusMessage = 'Sprite-sheet creation cancelled.';
				return;
			}

			statusMessage = 'Downloading atlas...';
			const atlasBlob = await downloadSpriteSheet(created.job_id);
			if (runId !== activeRun) return;
			resultPreviewUrl = URL.createObjectURL(atlasBlob);
			warningMessage = completed.warnings.join(' ') || null;
			if (warningMessage) addNotification('warning', 'Atlas warning', warningMessage);
			addNotification('info', 'Atlas ready', 'Inspect the generated atlas, then download its PNG or JSON metadata.');
			statusMessage = 'Sprite atlas complete.';
		} catch (error) {
			if (runId !== activeRun) return;
			const context = { action: 'create atlas', jobId: currentJobId };
			logUiError(error, context);
			errorMessage = userErrorMessage(error, context);
			addNotification('error', 'Atlas creation failed', errorMessage);
			statusMessage = 'Sprite-sheet creation failed.';
		} finally {
			if (runId === activeRun) {
				isProcessing = false;
				isCancelling = false;
			}
		}
	}

	async function requestCancel() {
		if (!currentJobId || isCancelling) return;
		const runId = activeRun;
		isCancelling = true;
		statusMessage = 'Cancelling atlas job...';
		try {
			const cancelled = await cancelSpriteSheetJob(currentJobId);
			if (runId !== activeRun) return;
			metadata = cancelled;
			statusMessage = metadata.status === 'cancelled' ? 'Sprite-sheet creation cancelled.' : `Job is already ${metadata.status}.`;
			addNotification('info', 'Processing stopped', statusMessage);
		} catch (error) {
			if (runId !== activeRun) return;
			const context = { action: 'cancel atlas', jobId: currentJobId };
			logUiError(error, context);
			errorMessage = userErrorMessage(error, context);
			addNotification('error', 'Cancel failed', errorMessage);
		} finally {
			if (runId === activeRun) {
				isProcessing = false;
				isCancelling = false;
			}
		}
	}

	async function waitForCompletion(jobId: string, runId: number): Promise<JobMetadata | null> {
		const deadline = Date.now() + JOB_TIMEOUT_MS;
		while (Date.now() < deadline) {
			const job = await getSpriteSheetJob(jobId);
			if (runId !== activeRun) return null;
			metadata = job;
			if (job.status === 'completed' || job.status === 'cancelled') return job;
			if (job.status === 'failed') throw new Error(job.error ?? 'Sprite-sheet job failed.');
			statusMessage = job.stage_message ?? `Packing sprite atlas... ${job.status}`;
			await new Promise((resolve) => setTimeout(resolve, JOB_POLL_INTERVAL_MS));
		}
		if (runId !== activeRun) return null;
		throw new Error('Sprite-sheet job timed out.');
	}

	async function downloadMetadata() {
		if (!currentJobId) return;
		try {
			const jobId = currentJobId;
			const url = URL.createObjectURL(await downloadSpriteSheetMetadata(jobId));
			const link = document.createElement('a');
			link.href = url;
			link.download = 'pixelreforge-sprite-sheet.json';
			link.click();
			window.setTimeout(() => URL.revokeObjectURL(url), 0);
		} catch (error) {
			const context = { action: 'download atlas metadata', jobId: currentJobId };
			logUiError(error, context);
			errorMessage = userErrorMessage(error, context);
			addNotification('error', 'Metadata download failed', errorMessage);
		}
	}

	function clearResult() {
		metadata = null;
		if (resultPreviewUrl) URL.revokeObjectURL(resultPreviewUrl);
		resultPreviewUrl = null;
	}

	function setSourcePreview(url: string | null) {
		if (sourcePreviewUrl) URL.revokeObjectURL(sourcePreviewUrl);
		sourcePreviewUrl = url;
	}

	function isSupportedImage(file: File): boolean {
		const fileName = file.name.toLowerCase();
		return SUPPORTED_IMAGE_ACCEPT.some((format) => file.type === format.mime || fileName.endsWith(format.extension));
	}

	function isJpegFile(file: File): boolean {
		const fileName = file.name.toLowerCase();
		return file.type === 'image/jpeg' || fileName.endsWith('.jpg') || fileName.endsWith('.jpeg');
	}

	function addNotification(tone: NotificationTone, title: string, message: string) {
		const id = nextNotificationId;
		const autoDismissMs = tone === 'error' ? undefined : NOTIFICATION_AUTO_DISMISS_MS;
		notifications = [...notifications, { id, tone, title, message, autoDismissMs }];
		nextNotificationId += 1;
		if (autoDismissMs) {
			notificationTimers.set(id, window.setTimeout(() => dismissNotification(id), autoDismissMs));
		}
	}

	function dismissNotification(id: number) {
		const timer = notificationTimers.get(id);
		if (timer) window.clearTimeout(timer);
		notificationTimers.delete(id);
		notifications = notifications.filter((notification) => notification.id !== id);
	}

	function clearNotifications() {
		for (const timer of notificationTimers.values()) window.clearTimeout(timer);
		notificationTimers.clear();
		notifications = [];
	}
</script>

<svelte:head>
	<title>Build sprite atlas - PixelReForge</title>
	<meta name="description" content="Pack individual sprites or an existing sheet into a downloadable pixel-art atlas with precise spacing, trimming, and JSON metadata." />
</svelte:head>

<main class="app-shell px-4 py-6 sm:px-8 lg:px-14 lg:py-9">
	<section class="mx-auto mb-7 flex max-w-6xl flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
		<div>
			<a class="readable-copy text-sm text-[var(--color-text-muted)] hover:text-[var(--color-accent-strong)]" href="/">← Back to landing</a>
			<p class="mt-4 text-lg uppercase tracking-[0.24em] text-[var(--color-accent)]">PixelReForge tools</p>
			<h1 class="mt-2 max-w-4xl text-5xl leading-[1.02] sm:text-7xl">Build pixel-art sprite sheets.</h1>
			<p class="readable-copy mt-3 max-w-2xl text-lg leading-8 text-[var(--color-text-muted)]">Pack a series of sprites or split an existing sheet, inspect the atlas at pixel level, and export its coordinates.</p>
		</div>
		<a class="readable-copy text-sm text-[var(--color-text-muted)] hover:text-[var(--color-accent-strong)]" href="/process">Restore pixel art →</a>
	</section>

	<section class="mx-auto grid w-full max-w-6xl min-w-0 gap-5" aria-label="Sprite atlas workflow">
		<SpriteUploadPanel {inputMode} {selectedFiles} {sourcePreviewUrl} {isProcessing} bind:isDragging onInputModeChange={changeInputMode} onFilesSelected={selectFiles} onRemoveFile={removeFile} />
		<AtlasSettingsPanel bind:settings {inputMode} selectedFilesCount={selectedFiles.length} {isProcessing} {isCancelling} {statusMessage} {warningMessage} {errorMessage} onCreate={createAtlas} onCancel={requestCancel} />
		<AtlasResultPanel {isProcessing} atlasPreviewUrl={resultPreviewUrl} {statusMessage} {metadata} onDownloadMetadata={downloadMetadata} />
	</section>
</main>

<NotificationStack {notifications} onDismiss={dismissNotification} />
