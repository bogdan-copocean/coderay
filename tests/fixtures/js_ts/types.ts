/**
 * Shared types for API layer.
 */

export interface RequestConfig {
    headers?: Record<string, string>;
    signal?: AbortSignal;
}

export interface Response<T> {
    ok: boolean;
    data: T;
    status: number;
}

export type UserId = string;
