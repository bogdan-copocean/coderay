/**
 * User service - production-like JS module.
 */

import { db } from '../db/client';
import { logger } from '../utils/logger';

const DEFAULT_LIMIT = 100;

export class UserService {
    constructor(repository) {
        this.repository = repository;
    }

    async fetchUsers(limit = DEFAULT_LIMIT) {
        const users = await this.repository.findAll({ limit });
        return users.map(u => this._toDTO(u));
    }

    async createUser(name, email) {
        const user = await this.repository.create({ name, email });
        logger.info('User created', { id: user.id });
        return this._toDTO(user);
    }

    _toDTO(user) {
        return { id: user.id, name: user.name, email: user.email };
    }
}

export function createUserService(repo) {
    return new UserService(repo);
}
