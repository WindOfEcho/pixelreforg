export type HelpText = {
	id: string;
	label: string;
	description: string;
	impact: string;
	example: string;
};

export type NotificationTone = 'info' | 'warning' | 'error';

export type UiNotification = {
	id: number;
	tone: NotificationTone;
	title: string;
	message: string;
};
