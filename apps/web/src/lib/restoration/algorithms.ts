import type { RestoreAlgorithm } from '$lib/types';

export type RestoreAlgorithmOption = {
	id: RestoreAlgorithm;
	label: string;
	helpId: string;
	shortDescription: string;
	description: string;
	supportsScale: boolean;
	supportsFractional: boolean;
	supportsColorBucket: boolean;
};

export const RESTORE_ALGORITHM_OPTIONS: RestoreAlgorithmOption[] = [
	{
		id: 'auto',
		label: 'Smart auto',
		helpId: 'algorithm-auto-help',
		shortDescription: 'Default. Selects an algorithm automatically.',
		description: 'Auto mode runs preflight analysis and selects Fast integer, Noisy pixel, or AI grid hypothesis depending on detected artifacts.',
		supportsScale: false,
		supportsFractional: false,
		supportsColorBucket: false
	},
	{
		id: 'integer-grid-v1',
		label: 'Fast integer',
		helpId: 'algorithm-integer-help',
		shortDescription: 'For clean pixel art.',
		description: 'Fast integer restores clean whole-number nearest-neighbor upscales with block majority voting.',
		supportsScale: true,
		supportsFractional: false,
		supportsColorBucket: false
	},
	{
		id: 'resampled-grid-v2',
		label: 'Resampled v2',
		helpId: 'algorithm-resampled-help',
		shortDescription: 'For fractional scale and known original size.',
		description: 'Resampled v2 restores non-integer upscales. Use manual scale or Advanced original size for best quality.',
		supportsScale: true,
		supportsFractional: true,
		supportsColorBucket: false
	},
	{
		id: 'noisy-pixel-v1',
		label: 'Noisy pixel',
		helpId: 'algorithm-noisy-help',
		shortDescription: 'For JPEG and AI artifacts.',
		description: 'Noisy pixel uses cluster-based reconstruction for JPEG and AI color artifacts. It can also use fractional manual scale or original size.',
		supportsScale: true,
		supportsFractional: true,
		supportsColorBucket: true
	},
	{
		id: 'ai-grid-hypothesis-v1',
		label: 'AI grid hypothesis',
		helpId: 'algorithm-ai-grid-help',
		shortDescription: 'Estimates a pixel grid for rough AI art.',
		description: 'AI grid hypothesis ranks candidate pixel grids, then uses clustering and isolated artifact cleanup. Use it for AI pixel art with uncertain grid boundaries or no clear source size.',
		supportsScale: true,
		supportsFractional: true,
		supportsColorBucket: true
	}
];

export function algorithmOptionFor(value: RestoreAlgorithm): RestoreAlgorithmOption | undefined {
	return RESTORE_ALGORITHM_OPTIONS.find((option) => option.id === value);
}

export function supportsScaleControls(value: RestoreAlgorithm): boolean {
	return algorithmOptionFor(value)?.supportsScale ?? false;
}

export function supportsFractionalControls(value: RestoreAlgorithm): boolean {
	return algorithmOptionFor(value)?.supportsFractional ?? false;
}

export function supportsColorBucketControls(value: RestoreAlgorithm): boolean {
	return algorithmOptionFor(value)?.supportsColorBucket ?? false;
}
