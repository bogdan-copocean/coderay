/**
 * API client - production-like TS module.
 */

import type { RequestConfig, Response as ApiResponse } from './types';

export interface ApiClientOptions {
    baseUrl: string;
    timeout?: number;
}

export class ApiClient {
    private baseUrl: string;
    private timeout: number;

    constructor(options: ApiClientOptions) {
        this.baseUrl = options.baseUrl;
        this.timeout = options.timeout ?? 5000;
    }

    async get<T>(path: string, config?: RequestConfig): Promise<ApiResponse<T>> {
        const url = `${this.baseUrl}${path}`;
        const res = await fetch(url, { ...config, method: 'GET' });
        return this._parseResponse<T>(res);
    }

    async post<T>(path: string, body: unknown): Promise<ApiResponse<T>> {
        const url = `${this.baseUrl}${path}`;
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        return this._parseResponse<T>(res);
    }

    private async _parseResponse<T>(res: globalThis.Response): Promise<ApiResponse<T>> {
        const data = await res.json();
        return { ok: res.ok, data, status: res.status };
    }
}

export const createApiClient = (options: ApiClientOptions) =>
    new ApiClient(options);
