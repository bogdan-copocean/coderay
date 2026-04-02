/**
 * Canonical JS/TS concepts for skeleton extraction tests.
 */

import { UserRepository } from '../../fixtures/js_ts/app/data/userRepository';
import type { ApiResponse, UserRecord } from '../../fixtures/js_ts/app/types';

type Handler<T> = (value: T) => T;

interface ServiceContract {
    loadProfile(userId: number): Promise<ApiResponse<UserRecord>>;
}

class CoreService implements ServiceContract {
    constructor(private readonly repository: UserRepository) {}

    async loadProfile(userId: number): Promise<ApiResponse<UserRecord>> {
        const user = this.repository.findById(userId);
        if (!user) {
            throw new Error('not_found');
        }
        return { ok: true, data: user };
    }

    withClosure(prefix: string): Handler<string> {
        const wrapper = (value: string): string => `${prefix}:${value}`;
        return wrapper;
    }
}

export async function buildProfileLabel(userId: number): Promise<string> {
    const repository = new UserRepository();
    const service = new CoreService(repository);
    const profile = await service.loadProfile(userId);
    const format = service.withClosure('user');
    return format(profile.data.email.toLowerCase());
}

export const buildService = (): CoreService => {
    return new CoreService(new UserRepository());
};

