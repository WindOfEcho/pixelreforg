import { dev } from '$app/environment';

export class ApiError extends Error {
	constructor(
		message: string,
		readonly status: number,
		readonly endpoint: string,
		readonly responseBody: string
	) {
		super(message);
		this.name = 'ApiError';
	}
}

export type ErrorContext = {
	action: string;
	jobId?: string | null;
	endpoint?: string;
};

export function userErrorMessage(error: unknown, context: ErrorContext): string {
	if (dev) {
		return debugMessage(error, context);
	}

	if (error instanceof ApiError) {
		if (error.status === 400 || error.status === 415) return isSpriteSheetAction(context.action) ? 'The selected sprites cannot be processed. Try PNG, JPEG, GIF, or WebP.' : 'The selected image cannot be processed. Try PNG, JPEG, GIF, or WebP.';
		if (error.status === 404) return isSpriteSheetAction(context.action) ? 'This sprite-sheet job is no longer available. Upload the sprites again.' : 'This processing job is no longer available. Upload the image again.';
		if (error.status >= 500) return isSpriteSheetAction(context.action) ? 'The sprite-sheet service failed. Please try again in a moment.' : 'The processing service failed. Please try again in a moment.';
	}

	if (isSpriteSheetAction(context.action)) {
		return context.action.startsWith('cancel') ? 'Could not cancel the current atlas job. Please try again.' : 'Sprite-sheet creation failed. Check the image inputs and settings, then try again.';
	}
	return context.action === 'cancel' ? 'Could not cancel the current restoration. Please try again.' : 'Restoration failed. Check the image format and try again.';
}

export function logUiError(error: unknown, context: ErrorContext) {
	const details = {
		action: context.action,
		jobId: context.jobId ?? null,
		endpoint: context.endpoint ?? (error instanceof ApiError ? error.endpoint : null),
		status: error instanceof ApiError ? error.status : null,
		cause: error instanceof Error ? error.message : String(error)
	};

	console.error('[PixelReForge UI error]', details, error);
}

function debugMessage(error: unknown, context: ErrorContext): string {
	const base = error instanceof Error ? error.message : String(error);
	const parts = [`${context.action}: ${base}`];

	if (context.jobId) parts.push(`job=${context.jobId}`);
	if (error instanceof ApiError) parts.push(`status=${error.status}`, `endpoint=${error.endpoint}`);

	return parts.join(' | ');
}

function isSpriteSheetAction(action: string): boolean {
	return action.includes('atlas');
}
