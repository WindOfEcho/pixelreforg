import type { ClassValue } from 'clsx';
import { cn } from '$lib/utils';

export type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type Size = 'sm' | 'md' | 'lg';

const base =
	'inline-flex items-center justify-center rounded-2xl font-black tracking-[0.12em] transition hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--color-accent-strong)] disabled:pointer-events-none disabled:opacity-55';

const variants: Record<Variant, string> = {
	primary: 'bg-[var(--color-accent)] text-[var(--color-bg-deep)] hover:bg-[var(--color-accent-strong)]',
	secondary: 'border border-[var(--color-border)] bg-[var(--color-surface-strong)] text-[var(--color-text-muted)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]',
	ghost: 'border border-transparent bg-transparent text-[var(--color-text-muted)] hover:border-[var(--color-border)] hover:text-[var(--color-text)]',
	danger: 'border border-[var(--color-danger)] bg-[var(--color-bg-deep)] text-[var(--color-danger)] hover:bg-[var(--color-bg)]'
};

const sizes: Record<Size, string> = {
	sm: 'min-h-9 px-3 text-sm',
	md: 'min-h-11 px-4 text-lg',
	lg: 'min-h-14 px-7 text-2xl'
};

export function buttonClass(
	variant: Variant = 'primary',
	size: Size = 'md',
	className?: ClassValue
) {
	return cn(base, variants[variant], sizes[size], className);
}