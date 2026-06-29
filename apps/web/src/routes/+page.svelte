<script lang="ts">
	import HeroSection from '$lib/components/restoration/HeroSection.svelte';
	import NotificationStack from '$lib/components/restoration/NotificationStack.svelte';
	import ResultPanel from '$lib/components/restoration/ResultPanel.svelte';
	import SettingsPanel from '$lib/components/restoration/SettingsPanel.svelte';
	import UploadPanel from '$lib/components/restoration/UploadPanel.svelte';
	import { cancelJob, createJob, downloadResult, getJob } from '$lib/api';
	import type { JobMetadata, RestoreSettings, ScaleMode } from '$lib/types';
	import type { NotificationTone, UiNotification } from '$lib/ui/types';

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
	<HeroSection />

	<section class="flow" aria-label="Image restoration workflow">
		<UploadPanel
			{selectedFile}
			{sourcePreviewUrl}
			bind:isDragging
			onFileSelected={selectFile}
		/>

		<SettingsPanel
			bind:scaleMode
			bind:manualScale
			bind:minScale
			bind:maxScale
			bind:confidenceThreshold
			bind:originalWidth
			bind:originalHeight
			{selectedFile}
			{isProcessing}
			{isCancelling}
			{statusMessage}
			{warningMessage}
			{errorMessage}
			onRestore={restoreImage}
			onCancel={requestCancel}
		/>

		<ResultPanel {isProcessing} {resultPreviewUrl} {statusMessage} {metadata} />
	</section>
</main>

<NotificationStack {notifications} onDismiss={dismissNotification} />
