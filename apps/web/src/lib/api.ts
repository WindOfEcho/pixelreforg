import type { JobCreateResponse, JobMetadata, RestoreSettings } from './types';

export const API_BASE_URL = 'http://localhost:8000';

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

	const response = await fetch(`${API_BASE_URL}/api/jobs?${params.toString()}`, {
		method: 'POST',
		body: formData
	});

	if (!response.ok) {
		throw new Error(await responseText(response, 'Failed to create processing job.'));
	}

	return response.json() as Promise<JobCreateResponse>;
}

export async function getJob(jobId: string): Promise<JobMetadata> {
	const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
	if (!response.ok) {
		throw new Error(await responseText(response, 'Failed to read processing job.'));
	}

	return response.json() as Promise<JobMetadata>;
}

export async function downloadResult(jobId: string): Promise<Blob> {
	const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/download`);
	if (!response.ok) {
		throw new Error(await responseText(response, 'Failed to download restored image.'));
	}

	return response.blob();
}

export async function cancelJob(jobId: string): Promise<JobMetadata> {
	const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/cancel`, {
		method: 'POST'
	});
	if (!response.ok) {
		throw new Error(await responseText(response, 'Failed to cancel processing job.'));
	}

	return response.json() as Promise<JobMetadata>;
}

async function responseText(response: Response, fallback: string): Promise<string> {
	const text = await response.text();
	return text || fallback;
}
