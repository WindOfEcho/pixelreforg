export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
export type ScaleMode = 'auto' | 'manual';
export type RestoreAlgorithm = 'auto' | 'integer-grid-v1' | 'resampled-grid-v2' | 'noisy-pixel-v1';
export type PaletteCleanupMode = 'off' | 'light' | 'medium' | 'strong' | 'custom';

export type RestoreSettings = {
	algorithm: RestoreAlgorithm;
	scaleMode: ScaleMode;
	manualScale: number;
	minScale: number;
	maxScale: number;
	originalWidth?: number;
	originalHeight?: number;
	paletteCleanup: PaletteCleanupMode;
	paletteMergeDistance?: number;
	paletteTargetColors?: number;
	noisyColorBucketSize: number;
	confidenceThreshold: number;
};

export type JobCreateResponse = {
	job_id: string;
	status: JobStatus;
	status_url: string;
	download_url: string;
};

export type JobMetadata = {
	job_id: string;
	status: JobStatus;
	input_filename: string;
	input_path: string;
	output_path: string | null;
	algorithm_requested: string | null;
	algorithm_used: string | null;
	algorithm_version: string | null;
	source_size: [number, number] | null;
	target_size: [number, number] | null;
	original_size_override: [number, number] | null;
	scale_x: number | null;
	scale_y: number | null;
	scale_method: string | null;
	confidence: number | null;
	palette_cleanup: string | null;
	analysis: Record<string, unknown> | null;
	palette: Record<string, unknown> | null;
	reconstruction: Record<string, unknown> | null;
	warnings: string[];
	error: string | null;
};
