export const verifyWithCallback = (
    token: string,
    done: (err: Error | null, status: 'valid' | 'invalid') => void,
): void => {
    setTimeout(() => {
        if (token.startsWith('ok:')) {
            done(null, 'valid');
            return;
        }
        done(new Error('invalid token'), 'invalid');
    }, 0);
};

export const verifyAsync = async (token: string): Promise<'valid' | 'invalid'> => {
    return new Promise((resolve) => {
        verifyWithCallback(token, (err, status) => {
            if (err) {
                resolve('invalid');
                return;
            }
            resolve(status);
        });
    });
};
