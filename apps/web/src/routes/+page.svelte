<script lang="ts">
	import mascot from '$lib/assets/pixelreforge-icon-Zephyr-fox-x20-outline.png';
</script>

<svelte:head>
	<title>PixelReForge - Restore pixel art to its original form</title>
	<meta
		name="description"
		content="PixelReForge restores enlarged pixel art back toward its original crisp form. Upload an image, choose scale detection, compare the result, and download PNG output."
	/>
</svelte:head>

<main class="app-shell px-4 py-8 sm:px-8 lg:px-14">
	<section class="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
		<div class="space-y-8">
			<p class="text-lg uppercase tracking-[0.28em] text-[var(--color-accent)]">PixelReForge</p>
			<div class="space-y-5">
				<h1 class="max-w-4xl text-6xl leading-[0.95] tracking-[0.02em] text-[var(--color-text)] sm:text-7xl lg:text-8xl">
					Restore pixel art to its original form.
				</h1>
				<p class="readable-copy max-w-2xl text-lg leading-8 text-[var(--color-text-muted)] sm:text-xl">
					Upload an enlarged sprite or tile, let PixelReForge detect the scale, then compare the restored image before downloading a crisp PNG.
				</p>
			</div>

			<div class="flex flex-col gap-3 sm:flex-row">
				<a
					class="inline-flex min-h-14 items-center justify-center rounded-2xl bg-[var(--color-accent)] px-7 text-2xl font-black tracking-[0.12em] text-[var(--color-bg-deep)] transition hover:-translate-y-0.5 hover:bg-[var(--color-accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--color-accent-strong)]"
					href="/process"
				>
					Start restoring
				</a>
				<a
					class="inline-flex min-h-14 items-center justify-center rounded-2xl border border-[var(--color-border)] px-7 text-2xl font-black tracking-[0.12em] text-[var(--color-text)] transition hover:-translate-y-0.5 hover:border-[var(--color-border-strong)]"
					href="#how-it-works"
				>
					How it works
				</a>
			</div>

			<div id="how-it-works" class="grid gap-3 sm:grid-cols-3">
				{#each ['Upload pixel art', 'Detect scale', 'Compare and download'] as item (item)}
					<div class="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-panel)] backdrop-blur">
						<p class="text-2xl text-[var(--color-text)]">{item}</p>
					</div>
				{/each}
			</div>
		</div>

		<div class="rounded-[2rem] border border-[var(--color-border)] bg-[linear-gradient(145deg,rgba(248,221,164,0.12),rgba(203,128,125,0.1))] p-6 shadow-[var(--shadow-panel)]">
			<figure class="grid place-items-center gap-4">
				<img class="pixelated w-full max-w-sm" src={mascot} alt="PixelReForge fox mascot" />
				<figcaption class="readable-copy text-center text-sm text-[var(--color-text-soft)]">
					Zephyr by WindOfEcho © 2026 · CC BY-NC-ND 4.0
				</figcaption>
			</figure>
		</div>
	</section>
</main>
