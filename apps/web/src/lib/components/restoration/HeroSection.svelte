<script lang="ts">
	import mascot from '$lib/assets/pixelreforge-icon-Zephyr-fox-x20-outline.png';
</script>

<section class="mx-auto mb-7 grid max-w-6xl items-end gap-6 lg:grid-cols-[1fr_20rem]">
	<div>
		<p class="mb-3 text-lg uppercase tracking-[0.24em] text-[var(--color-accent)]">PixelReForge MVP</p>
		<h1 class="max-w-4xl text-5xl leading-[1.02] sm:text-7xl">Restore pixel art to its original form.</h1>
		<p class="readable-copy mt-5 max-w-2xl text-xl leading-8 text-[var(--color-text-muted)]">
			Upload an enlarged pixel art image, choose how scale should be detected, and download a restored PNG.
		</p>
	</div>
	<div class="grid aspect-square min-h-56 place-items-center overflow-hidden rounded-[2rem] border border-[var(--color-border)] bg-[linear-gradient(145deg,rgba(248,221,164,0.12),rgba(203,128,125,0.1))] shadow-[var(--shadow-panel)]" aria-hidden="true">
		<figure class="grid place-items-center">
			<img src={mascot} alt="PixelReForge mascot" class="pixelated relative z-10 w-[94%] object-contain" />
			<figcaption class="readable-copy text-center text-xs text-[var(--color-text-soft)] opacity-40">
				Zephyr by WindOfEcho © 2026 · CC BY-NC-ND 4.0
			</figcaption>
		</figure>
	</div>
</section>
