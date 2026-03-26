import { UserRepository } from '../data/userRepository';
import { formatUserLabel } from './internal/formatters';
import { logInfo } from '../shared/logger';
import { BaseService } from './baseService';
import { verifyAsync } from './internal/callbacks';
import type { ApiResponse, UserRecord } from '../types';

const createSuffixer = (suffix: string) => {
    return (value: string): string => `${value}${suffix}`;
};

export const getPrimaryEmail = (repository: UserRepository, userId: number): string | null => {
    return repository.findById(userId)?.email?.toLowerCase() ?? null;
};

export class UserService extends BaseService {
    constructor(private readonly repository: UserRepository) {}

    loadProfile(userId: number): { id: number; label: string; email: string | null } | null {
        const user = this.repository.findById(userId);
        if (!user) {
            return null;
        }
        const suffix = createSuffixer(' [fixture]');
        const label = suffix(formatUserLabel(user));
        logInfo('profile_loaded', { userId });
        return {
            id: user.id,
            label,
            email: getPrimaryEmail(this.repository, userId),
        };
    }

    async loadProfileAsync(
        userId: number,
        token: string,
    ): Promise<ApiResponse<{ id: number; label: string; score: number }>> {
        const profile = this.loadProfile(userId);
        if (!profile) {
            return { ok: false, data: { id: userId, label: 'not_found', score: 0 } };
        }
        const status = await verifyAsync(token);
        const { formatScore } = await import('./internal/formatters');
        const processed = this.processPayload({ id: profile.id, status });
        return {
            ok: status === 'valid',
            data: {
                id: profile.id,
                label: `${profile.label}:${String(processed.status)}`,
                score: formatScore(profile.id),
            },
        };
    }
}

export const mapUsers = <T>(users: UserRecord[], mapper: (user: UserRecord) => T): T[] => {
    return users.map((user) => mapper(user));
};
