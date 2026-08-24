<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import { SUPPORTED_IMAGE_ACCEPT_VALUE } from '$lib/components/restoration/UploadPanel.svelte';
	import type { SpriteSheetInputMode } from '$lib/types';

	let {
		inputMode,
		selectedFiles,
		sourcePreviewUrl,
		isProcessing,
		isDragging = $bindable(false),
		onInputModeChange,
		onFilesSelected,
		onRemoveFile
	}: {
		inputMode: SpriteSheetInputMode;
		selectedFiles: File[];
		sourcePreviewUrl: string | null;
		isProcessing: boolean;
		isDragging: boolean;
		onInputModeChange: (mode: SpriteSheetInputMode) => void;
		onFilesSelected: (files: File[]) => void;
		onRemoveFile: (index: number) => void;
	} = $props();

	function handleFileInput(event: Event) {
		if (isProcessing) return;
		const input = event.currentTarget as HTMLInputElement;
		onFilesSelected(Array.from(input.files ?? []));
		input.value = '';
	}

	function handleDrop(event: DragEvent) {
		if (isProcessing) return;
		event.preventDefault();
		isDragging = false;
		onFilesSelected(Array.from(event.dataTransfer?.files ?? []));
	}

	function formatFileSize(bytes: number): string {
		if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function modeClass(active: boolean) {
		return active
			? 'border-[rgba(248,221,164,0.72)] bg-[rgba(223,137,56,0.16)] text-[var(--color-text)]'
			: 'border-[var(--color-border)] bg-[rgba(47,38,48,0.52)] text-[var(--color-text-muted)]';
	}
</script>

<section class="rounded-[1.75rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-panel)] backdrop-blur md:p-7" aria-labelledby="sprite-upload-title">
	<div class="mb-5 flex items-end justify-between gap-4">
		<p class="text-xl uppercase tracking-[0.18em] text-[var(--color-accent)]">Step 1</p>
		<h2 id="sprite-upload-title" class="text-4xl">Choose sprites</h2>
	</div>

	<div class="mb-4 grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Sprite input mode">
		<label class={[modeClass(inputMode === 'files'), 'flex min-h-20 cursor-pointer flex-col justify-center gap-1 rounded-2xl border px-4 py-3 text-xl']}>
			<span class="flex items-center gap-2"><input type="radio" name="sprite-input-mode" checked={inputMode === 'files'} onchange={() => onInputModeChange('files')} disabled={isProcessing} /> Separate files</span>
			<small class="readable-copy text-sm text-[var(--color-text-muted)]">Pack a sequence of individual sprites.</small>
		</label>
		<label class={[modeClass(inputMode === 'sheet'), 'flex min-h-20 cursor-pointer flex-col justify-center gap-1 rounded-2xl border px-4 py-3 text-xl']}>
			<span class="flex items-center gap-2"><input type="radio" name="sprite-input-mode" checked={inputMode === 'sheet'} onchange={() => onInputModeChange('sheet')} disabled={isProcessing} /> Existing sheet</span>
			<small class="readable-copy text-sm text-[var(--color-text-muted)]">Split and repack one sprite sheet or atlas.</small>
		</label>
	</div>

	<label
		class={[
			'grid min-h-52 cursor-pointer place-items-center gap-2 rounded-[1.35rem] border-2 border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface-soft)] p-8 text-center text-[var(--color-text)] transition hover:-translate-y-0.5 hover:bg-[rgba(248,221,164,0.14)] hover:shadow-[0_10px_30px_rgba(47,38,48,0.25)] focus-within:outline-2 focus-within:outline-offset-4 focus-within:outline-[var(--color-accent-strong)]',
			isDragging && '-translate-y-0.5 border-[var(--color-accent-strong)] bg-[rgba(248,221,164,0.18)]',
			isProcessing && 'cursor-not-allowed opacity-55'
		]}
		for="sprite-file-input"
		ondragover={(event) => {
			if (isProcessing) return;
			event.preventDefault();
			isDragging = true;
		}}
		ondragleave={() => {
			if (isProcessing) return;
			isDragging = false;
		}}
		ondrop={handleDrop}
	>
		<strong class="text-4xl">{inputMode === 'files' ? 'Drop sprites here' : 'Drop a sprite sheet here'}</strong>
		<p class="m-0 text-2xl text-[var(--color-text-muted)]">or click to select</p>
		<span class="readable-copy text-sm text-[var(--color-text-muted)]">PNG, JPEG, GIF, or WebP input</span>
	</label>
	<input id="sprite-file-input" type="file" accept={SUPPORTED_IMAGE_ACCEPT_VALUE} multiple={inputMode === 'files'} onchange={handleFileInput} disabled={isProcessing} hidden />

	{#if sourcePreviewUrl && inputMode === 'sheet'}
		<div class="pixel-preview mt-4 grid min-h-60 place-items-center overflow-hidden rounded-[1.25rem] p-4">
			<img class="pixelated max-h-[28rem] object-contain" src={sourcePreviewUrl} alt="Selected sprite sheet preview" />
		</div>
	{/if}

	{#if selectedFiles.length > 0}
		<div class="readable-copy mt-4 rounded-[1.25rem] bg-[var(--color-surface-soft)] p-4">
			<div class="mb-3 flex items-center justify-between gap-3">
				<p class="m-0 text-sm text-[var(--color-text-muted)]">{selectedFiles.length} {selectedFiles.length === 1 ? 'image ready' : 'images ready'}</p>
				{#if inputMode === 'files'}<span class="text-sm text-[var(--color-text-soft)]">Names become frame names</span>{/if}
			</div>
			<ul class="m-0 grid list-none gap-2 p-0">
				{#each selectedFiles as file, index (file)}
					<li class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-xl bg-[rgba(47,38,48,0.42)] px-3 py-2">
						<div class="min-w-0">
							<p class="m-0 truncate text-[var(--color-text)]">{file.name}</p>
							<p class="m-0 text-sm text-[var(--color-text-muted)]">{formatFileSize(file.size)}</p>
						</div>
						<Button variant="ghost" size="sm" type="button" onclick={() => onRemoveFile(index)} disabled={isProcessing}>Remove</Button>
					</li>
				{/each}
			</ul>
		</div>
	{/if}
</section>
