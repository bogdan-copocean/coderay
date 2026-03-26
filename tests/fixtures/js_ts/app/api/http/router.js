import { UserRepository } from '../../data/userRepository';
import { UserService } from '../../services/userService';
import { getUserProfile, getUserProfileAsync } from '../controllers/userController';

export function registerRoutes() {
    return {
        '/users/:id': (id) => {
            const repository = new UserRepository();
            const service = new UserService(repository);
            return getUserProfile(service, Number(id));
        },
        '/users/:id/secure': async (id, token) => {
            const repository = new UserRepository();
            const service = new UserService(repository);
            return getUserProfileAsync(service, Number(id), token);
        },
    };
}
