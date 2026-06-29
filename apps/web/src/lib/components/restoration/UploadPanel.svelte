<script lang="ts">
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
</script>

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
