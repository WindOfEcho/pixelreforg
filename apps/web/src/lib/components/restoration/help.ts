import type { HelpText } from '$lib/ui/types';

const helpItems: HelpText[] = [
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
	},
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

export function helpFor(id: string): HelpText {
	return helpItems.find((item) => item.id === id)!;
}
