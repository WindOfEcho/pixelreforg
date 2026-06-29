export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
export type ScaleMode = 'auto' | 'manual';

export type RestoreSettings = {
	scaleMode: ScaleMode;
	manualScale: number;
	minScale: number;
	maxScale: number;
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
	source_size: [number, number] | null;
	target_size: [number, number] | null;
	scale_x: number | null;
	scale_y: number | null;
	scale_method: string | null;
	confidence: number | null;
	warnings: string[];
	error: string | null;
};
