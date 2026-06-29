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

	<label
		class:dragging={isDragging}
		class="dropzone"
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
		<strong>Drop image here</strong>
		<p>or click to select</p>
		<span>PNG, JPEG, GIF, or WebP input</span>
	</label>

	<input
		id="file-input"
		type="file"
		accept="image/*"
		onchange={handleFileInput}
		hidden
	/>

	{#if selectedFile}
		<p class="file-line">Selected: {selectedFile.name} ({Math.round(selectedFile.size / 1024)} KB)</p>
	{/if}

	{#if sourcePreviewUrl}
		<div class="preview-card source-preview">
			<img src={sourcePreviewUrl} alt="Selected source preview" />
		</div>
	{/if}
</section>
