<script lang="ts" module>
	export const SUPPORTED_IMAGE_ACCEPT = [
		{ mime: 'image/png', extension: '.png' },
		{ mime: 'image/jpeg', extension: '.jpg' },
		{ mime: 'image/jpeg', extension: '.jpeg' },
		{ mime: 'image/gif', extension: '.gif' },
		{ mime: 'image/webp', extension: '.webp' }
	];

	export const SUPPORTED_IMAGE_ACCEPT_VALUE = SUPPORTED_IMAGE_ACCEPT.flatMap((format) => [format.mime, format.extension]).join(',');
</script>

<script lang="ts">
	let imageWidth = $state<number | null>(null);
	let imageHeight = $state<number | null>(null);
	let imageInfoUrl = $state<string | null>(null);

	let {
		selectedFile,
		sourcePreviewUrl,
		isDragging = $bindable(false),
		onFileSelected
	}: {
		selectedFile: File | null;
		sourcePreviewUrl: string | null;
		isDragging: boolean;
		onFileSelected: (file: File | null) => void;
	} = $props();

	function handleFileInput(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		onFileSelected(input.files?.[0] ?? null);
	}

	function handleDrop(event: DragEvent) {
		event.preventDefault();
		isDragging = false;
		onFileSelected(event.dataTransfer?.files?.[0] ?? null);
	}

	function handlePreviewLoad(event: Event) {
		const image = event.currentTarget as HTMLImageElement;
		imageWidth = image.naturalWidth;
		imageHeight = image.naturalHeight;
		imageInfoUrl = sourcePreviewUrl;
	}

	function formatFileSize(bytes: number): string {
		if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function formatImageType(file: File): string {
		return file.type.replace('image/', '').toUpperCase() || 'unknown type';
	}
</script>

<section class="rounded-[1.75rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-panel)] backdrop-blur md:p-7" aria-labelledby="upload-title">
	<div class="mb-5 flex items-end justify-between gap-4">
		<p class="text-xl uppercase tracking-[0.18em] text-[var(--color-accent)]">Step 1</p>
		<h2 id="upload-title" class="text-4xl">Upload image</h2>
	</div>

	<label
		class={[
			'grid min-h-52 cursor-pointer place-items-center gap-2 rounded-[1.35rem] border-2 border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface-soft)] p-8 text-center text-[var(--color-text)] transition hover:-translate-y-0.5 hover:bg-[rgba(248,221,164,0.14)] hover:shadow-[0_10px_30px_rgba(47,38,48,0.25)] focus-within:outline-2 focus-within:outline-offset-4 focus-within:outline-[var(--color-accent-strong)]',
			isDragging && '-translate-y-0.5 border-[var(--color-accent-strong)] bg-[rgba(248,221,164,0.18)]'
		]}
		for="file-input"
		ondragover={(event) => {
			event.preventDefault();
			isDragging = true;
		}}
		ondragleave={() => {
			isDragging = false;
		}}
		ondrop={handleDrop}
	>
		<strong class="text-4xl">Drop image here</strong>
		<p class="m-0 text-2xl text-[var(--color-text-muted)]">or click to select</p>
		<span class="readable-copy text-sm text-[var(--color-text-muted)]">PNG, JPEG, GIF, or WebP input</span>
	</label>

	<input id="file-input" type="file" accept={SUPPORTED_IMAGE_ACCEPT_VALUE} onchange={handleFileInput} hidden />

	{#if sourcePreviewUrl}
		<div class="pixel-preview mt-4 grid min-h-72 place-items-center overflow-hidden rounded-[1.25rem]">
			<img class="pixelated max-h-[32rem] object-contain" src={sourcePreviewUrl} alt="Selected source preview" onload={handlePreviewLoad} />
		</div>
	{/if}

	{#if selectedFile}
		<div class="readable-copy mt-4 grid gap-2 rounded-[1.25rem] bg-[var(--color-surface-soft)] p-4 text-sm text-[var(--color-text-muted)]">
			<p class="m-0 break-words text-[var(--color-text)]">Selected: {selectedFile.name}</p>
			<dl class="grid grid-cols-1 gap-2 sm:grid-cols-3">
				<div><dt class="text-[var(--color-text-soft)]">Format</dt><dd class="m-0 text-[var(--color-text)]">{formatImageType(selectedFile)}</dd></div>
				<div><dt class="text-[var(--color-text-soft)]">File size</dt><dd class="m-0 text-[var(--color-text)]">{formatFileSize(selectedFile.size)}</dd></div>
				<div><dt class="text-[var(--color-text-soft)]">Image size</dt><dd class="m-0 text-[var(--color-text)]">{imageInfoUrl === sourcePreviewUrl && imageWidth && imageHeight ? `${imageWidth} x ${imageHeight}` : 'loading...'}</dd></div>
			</dl>
		</div>
	{/if}
</section>
