import type { JobCreateResponse, JobMetadata, RestoreSettings, SpriteSheetInputMode, SpriteSheetSettings } from './types';
import { env } from '$env/dynamic/public';
import { ApiError } from '$lib/ui/errors';

export const API_BASE_URL = env.PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function createJob(file: File, settings: RestoreSettings): Promise<JobCreateResponse> {
	const formData = new FormData();
	formData.append('file', file);
	const params = new URLSearchParams({
		algorithm: settings.algorithm,
		scale_mode: settings.scaleMode,
		min_scale: String(validNumber(settings.minScale, 2)),
		max_scale: String(validNumber(settings.maxScale, 16)),
		palette_cleanup: settings.paletteCleanup,
		confidence_threshold: String(validNumber(settings.confidenceThreshold, 0.45)),
		fractional_scale_step: String(validNumber(settings.fractionalScaleStep, 0.25))
	});

	if (settings.scaleMode === 'manual' && isValidNumber(settings.manualScale)) {
		params.set('scale', String(settings.manualScale));
	}
	if (isValidNumber(settings.originalWidth)) {
		params.set('original_width', String(settings.originalWidth));
	}
	if (isValidNumber(settings.originalHeight)) {
		params.set('original_height', String(settings.originalHeight));
	}
	if (settings.paletteCleanup === 'custom' && isValidNumber(settings.paletteMergeDistance)) {
		params.set('palette_merge_distance', String(settings.paletteMergeDistance));
	}
	if (settings.paletteCleanup === 'custom' && isValidNumber(settings.paletteTargetColors)) {
		params.set('palette_target_colors', String(settings.paletteTargetColors));
	}
	if (isValidNumber(settings.noisyColorBucketSize)) {
		params.set('noisy_color_bucket_size', String(settings.noisyColorBucketSize));
	}

	const endpoint = `${API_BASE_URL}/api/jobs?${params.toString()}`;
	const response = await fetch(endpoint, {
		method: 'POST',
		credentials: 'include',
		body: formData
	});

	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to create processing job.');
	}

	return response.json() as Promise<JobCreateResponse>;
}

export async function getJob(jobId: string): Promise<JobMetadata> {
	const endpoint = `${API_BASE_URL}/api/jobs/${jobId}`;
	const response = await fetch(endpoint, { credentials: 'include' });
	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to read processing job.');
	}

	return response.json() as Promise<JobMetadata>;
}

export async function downloadResult(jobId: string): Promise<Blob> {
	const endpoint = `${API_BASE_URL}/api/jobs/${jobId}/download`;
	const response = await fetch(endpoint, { credentials: 'include' });
	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to download restored image.');
	}

	return response.blob();
}

export async function cancelJob(jobId: string): Promise<JobMetadata> {
	const endpoint = `${API_BASE_URL}/api/jobs/${jobId}/cancel`;
	const response = await fetch(endpoint, {
		method: 'POST',
		credentials: 'include'
	});
	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to cancel processing job.');
	}

	return response.json() as Promise<JobMetadata>;
}

export async function createSpriteSheetJob(
	files: File[],
	inputMode: SpriteSheetInputMode,
	settings: SpriteSheetSettings
): Promise<JobCreateResponse> {
	const formData = new FormData();
	for (const file of files) formData.append('files', file);
	const params = new URLSearchParams({
		input_mode: inputMode,
		packing_mode: settings.packingMode,
		trim_transparent: String(settings.trimTransparent),
		alpha_threshold: String(validNumber(settings.alphaThreshold, 0)),
		padding: String(validNumber(settings.padding, 1)),
		border_padding: String(validNumber(settings.borderPadding, 0)),
		extrude: String(validNumber(settings.extrude, 0)),
		max_width: String(validNumber(settings.maxWidth, 2048)),
		max_height: String(validNumber(settings.maxHeight, 2048)),
		power_of_two: String(settings.powerOfTwo),
		force_square: String(settings.forceSquare),
		allow_rotation: String(settings.allowRotation),
		sort_mode: settings.sortMode,
		include_metadata: String(settings.includeMetadata),
		extraction_mode: settings.extractionMode,
		offset_x: String(validNumber(settings.offsetX, 0)),
		offset_y: String(validNumber(settings.offsetY, 0)),
		gap_x: String(validNumber(settings.gapX, 0)),
		gap_y: String(validNumber(settings.gapY, 0))
	});
	setOptionalNumber(params, 'atlas_width', settings.atlasWidth);
	setOptionalNumber(params, 'atlas_height', settings.atlasHeight);
	setOptionalNumber(params, 'grid_columns', settings.gridColumns);
	setOptionalNumber(params, 'cell_width', settings.cellWidth);
	setOptionalNumber(params, 'cell_height', settings.cellHeight);
	setOptionalNumber(params, 'columns', settings.columns);
	setOptionalNumber(params, 'rows', settings.rows);
	if (settings.backgroundColor) params.set('background_color', settings.backgroundColor);

	const endpoint = `${API_BASE_URL}/api/sprite-sheets?${params.toString()}`;
	const response = await fetch(endpoint, {
		method: 'POST',
		credentials: 'include',
		body: formData
	});
	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to create sprite-sheet job.');
	}

	return response.json() as Promise<JobCreateResponse>;
}

export async function getSpriteSheetJob(jobId: string): Promise<JobMetadata> {
	const endpoint = `${API_BASE_URL}/api/sprite-sheets/${jobId}`;
	const response = await fetch(endpoint, { credentials: 'include' });
	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to read sprite-sheet job.');
	}

	return response.json() as Promise<JobMetadata>;
}

export async function downloadSpriteSheet(jobId: string): Promise<Blob> {
	const endpoint = `${API_BASE_URL}/api/sprite-sheets/${jobId}/download`;
	const response = await fetch(endpoint, { credentials: 'include' });
	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to download sprite atlas.');
	}

	return response.blob();
}

export async function downloadSpriteSheetMetadata(jobId: string): Promise<Blob> {
	const endpoint = `${API_BASE_URL}/api/sprite-sheets/${jobId}/metadata`;
	const response = await fetch(endpoint, { credentials: 'include' });
	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to download sprite metadata.');
	}

	return response.blob();
}

export async function cancelSpriteSheetJob(jobId: string): Promise<JobMetadata> {
	const endpoint = `${API_BASE_URL}/api/sprite-sheets/${jobId}/cancel`;
	const response = await fetch(endpoint, {
		method: 'POST',
		credentials: 'include'
	});
	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to cancel sprite-sheet job.');
	}

	return response.json() as Promise<JobMetadata>;
}

async function responseText(response: Response, fallback: string): Promise<string> {
	const text = await response.text();
	return text || fallback;
}

async function apiError(response: Response, endpoint: string, fallback: string): Promise<ApiError> {
	const body = await responseText(response, fallback);
	return new ApiError(body, response.status, endpoint, body);
}

function validNumber(value: number | null | undefined, fallback: number): number {
	return isValidNumber(value) ? value : fallback;
}

function setOptionalNumber(params: URLSearchParams, key: string, value: number | undefined): void {
	if (isValidNumber(value)) params.set(key, String(value));
}

function isValidNumber(value: number | null | undefined): value is number {
	return typeof value === 'number' && Number.isFinite(value);
}
