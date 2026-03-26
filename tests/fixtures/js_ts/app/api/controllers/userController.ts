import { UserService } from '../../services/userService';

export const getUserProfile = (
    userService: UserService,
    userId: number,
): { status: number; body: Record<string, unknown> } => {
    const profile = userService.loadProfile(userId);
    if (!profile) {
        return { status: 404, body: { error: 'not_found' } };
    }
    return { status: 200, body: profile };
};

export const getUserProfileAsync = async (
    userService: UserService,
    userId: number,
    token: string,
): Promise<{ status: number; body: Record<string, unknown> }> => {
    const result = await userService.loadProfileAsync(userId, token);
    if (!result.ok) {
        return { status: 401, body: { error: 'unauthorized' } };
    }
    return { status: 200, body: result.data };
};
