import type { JobCreateResponse, JobMetadata, RestoreSettings } from './types';
import { env } from '$env/dynamic/public';
import { ApiError } from '$lib/ui/errors';

export const API_BASE_URL = env.PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function createJob(file: File, settings: RestoreSettings): Promise<JobCreateResponse> {
	const formData = new FormData();
	formData.append('file', file);
	const params = new URLSearchParams({
		scale_mode: settings.scaleMode,
		min_scale: String(settings.minScale),
		max_scale: String(settings.maxScale),
		confidence_threshold: String(settings.confidenceThreshold)
	});

	if (settings.scaleMode === 'manual') {
		params.set('scale', String(settings.manualScale));
	}

	const endpoint = `${API_BASE_URL}/api/jobs?${params.toString()}`;
	const response = await fetch(endpoint, {
		method: 'POST',
		body: formData
	});

	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to create processing job.');
	}

	return response.json() as Promise<JobCreateResponse>;
}

export async function getJob(jobId: string): Promise<JobMetadata> {
	const endpoint = `${API_BASE_URL}/api/jobs/${jobId}`;
	const response = await fetch(endpoint);
	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to read processing job.');
	}

	return response.json() as Promise<JobMetadata>;
}

export async function downloadResult(jobId: string): Promise<Blob> {
	const endpoint = `${API_BASE_URL}/api/jobs/${jobId}/download`;
	const response = await fetch(endpoint);
	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to download restored image.');
	}

	return response.blob();
}

export async function cancelJob(jobId: string): Promise<JobMetadata> {
	const endpoint = `${API_BASE_URL}/api/jobs/${jobId}/cancel`;
	const response = await fetch(endpoint, {
		method: 'POST'
	});
	if (!response.ok) {
		throw await apiError(response, endpoint, 'Failed to cancel processing job.');
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
