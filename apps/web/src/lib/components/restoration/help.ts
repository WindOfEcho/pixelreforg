import type { HelpText } from '$lib/ui/types';

const helpItems: HelpText[] = [
	{
		id: 'algorithm-help',
		label: 'Algorithm',
		description: 'Selects the restoration pipeline used for the image.',
		impact: 'Fast integer is the stable default. Smart auto uses preflight analysis. Noisy pixel uses cluster-based reconstruction for JPEG and AI artifacts.',
		example: 'Use Fast integer for clean PNG upscales; use Smart auto or Noisy pixel for JPEG or AI-generated pixel art.'
	},
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
		description: 'The enlargement factor used to restore the original pixel size. Fractional algorithms accept decimal values.',
		impact: 'Higher values produce a smaller restored image. Wrong values can crush or duplicate details.',
		example: '4x turns 500 x 500 into 125 x 125. 1.5x turns 300 x 300 into 200 x 200.'
	},
	{
		id: 'auto-range-help',
		label: 'Auto scale range',
		description: 'Limits the scale candidates tested by auto detection.',
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
		id: 'palette-cleanup-help',
		label: 'Palette cleanup',
		description: 'Controls optional reduction of near-duplicate colors into a cleaner pixel-art palette.',
		impact: 'Off only records palette metadata. Light, medium, and strong merge similar restored colors with increasing aggressiveness.',
		example: 'Light cleanup can merge small JPEG color shifts; strong cleanup can force a cleaner but less detailed palette.'
	},
	{
		id: 'palette-merge-distance-help',
		label: 'Merge distance',
		description: 'Maximum color distance for merging near-duplicate colors in Custom palette cleanup.',
		impact: 'Lower values preserve more colors. Higher values create a cleaner but more simplified palette.',
		example: 'Use 8-16 for small JPEG shifts; use 24-40 for aggressive AI color cleanup.'
	},
	{
		id: 'palette-target-colors-help',
		label: 'Target colors',
		description: 'Optional maximum number of colors to keep after merging similar colors.',
		impact: 'Useful when you know the original palette was limited. Too low can erase intentional details.',
		example: 'Set 16 or 32 for simple sprites; leave empty when you only want similarity-based cleanup.'
	},
	{
		id: 'noisy-bucket-help',
		label: 'Color bucket size',
		description: 'Controls how broadly noisy-pixel-v1 groups similar colors inside each restored pixel block.',
		impact: 'Smaller buckets preserve detail; larger buckets tolerate stronger JPEG/AI color noise.',
		example: 'Use 12-16 for JPEG, 20-28 for rough AI-generated pixel art.'
	},
	{
		id: 'original-size-help',
		label: 'Original size override',
		description: 'Forces the restored output width and height when you know the original pixel-art size.',
		impact: 'This is the most reliable option for fractional scales such as 1.5x, 2.5x, 3.6x, or cropped inputs.',
		example: 'A 300 x 300 image enlarged from 200 x 200 is 1.5x and needs this future mode.'
	},
	{
		id: 'fractional-step-help',
		label: 'Fractional step',
		description: 'Controls the step used by auto detection when trying fractional scale candidates.',
		impact: 'Smaller values can find more candidates but are slower and may produce more ambiguous low-confidence results.',
		example: '0.25 tests 1.25x, 1.5x, 1.75x, 2x and so on.'
	}
];

export function helpFor(id: string): HelpText {
	return helpItems.find((item) => item.id === id)!;
}
