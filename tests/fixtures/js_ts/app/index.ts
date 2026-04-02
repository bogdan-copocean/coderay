import { registerRoutes } from './api/http/router';
import { StreamProcessor } from './services/internal/streaming';
import { UserRepository } from './data/userRepository';
import { mapUsers } from './services/userService';

export const startApp = (): Record<string, (id: string) => unknown> => {
    return registerRoutes();
};

export const bootstrap = async (): Promise<void> => {
    const repository = new UserRepository();
    const users = [repository.findById(1), repository.findById(2)].filter(Boolean);
    mapUsers(users, (user) => user.name);
    const processor = new StreamProcessor();
    async function* source() {
        yield { type: 'data' as const, value: 'hello' };
        yield { type: 'control' as const, value: 'done' };
    }
    for await (const _message of processor.process(source())) {
    }
};
