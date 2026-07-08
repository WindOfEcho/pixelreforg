import type { HelpText } from '$lib/ui/types';

const helpItems: HelpText[] = [
	{
		id: 'algorithm-help',
		label: 'Algorithm',
		description: 'Selects the restoration pipeline used for the image.',
		impact: 'Fast integer is the stable default. Smart auto uses preflight analysis. Noisy pixel handles JPEG artifacts. AI grid hypothesis targets rough generated pixel art.',
		example: 'Use Fast integer for clean PNG upscales; use Smart auto or Noisy pixel for JPEG; choose AI grid hypothesis when generated pixel art keeps its large size.'
	},
	{
		id: 'algorithm-auto-help',
		label: 'Smart auto',
		description: 'Runs preflight analysis and picks the safest available restoration path for the input.',
		impact: 'Best first try when you are not sure whether the image is clean or noisy.',
		example: 'Use it for mixed uploads where PNG, JPEG, and AI-generated images are possible.'
	},
	{
		id: 'algorithm-integer-help',
		label: 'Fast integer',
		description: 'Detects a whole-number upscale and samples one source pixel per restored pixel block.',
		impact: 'Fastest and sharpest option for clean nearest-neighbor upscales.',
		example: 'Use it for a clean 4x PNG sprite sheet that should become 1/4 of its current width and height.'
	},
	{
		id: 'algorithm-resampled-help',
		label: 'Resampled v2',
		description: 'Restores images enlarged with fractional or softened scaling instead of exact integer blocks.',
		impact: 'Useful when edges are slightly blurred or the original size is known, but it may need manual scale hints.',
		example: 'Use it for a 300 x 300 image that originally was 200 x 200.'
	},
	{
		id: 'algorithm-noisy-help',
		label: 'Noisy pixel',
		description: 'Groups similar colors inside each pixel block to tolerate JPEG compression and color noise.',
		impact: 'More robust on noisy files, but can simplify subtle palette differences.',
		example: 'Use it for a JPEG pixel-art image with speckled colors around edges.'
	},
	{
		id: 'algorithm-ai-grid-help',
		label: 'AI grid hypothesis',
		description: 'Scores candidate pixel grid sizes using reconstruction error, palette compactness, edge alignment, and scale priors for rough AI pixel art.',
		impact: 'Better when the generated image has no clean source scale, but slower because it ranks multiple grid hypotheses.',
		example: 'Use it when generated pixel art keeps the image too large or when pixel boundaries are uncertain.'
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
		description: 'Controls how broadly Noisy pixel and AI grid hypothesis group similar colors inside each restored pixel block.',
		impact: 'Smaller buckets preserve detail; larger buckets tolerate stronger JPEG or AI color noise during clustered reconstruction.',
		example: 'Use 12-16 for JPEG in Noisy pixel; use 20-28 for rough AI-generated pixel art in AI grid hypothesis.'
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
