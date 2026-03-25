/**
 * Service with callback-heavy methods — exercises Promise and nested callback patterns.
 */

export class TokenVerifier {
    constructor(private readonly publicKey: string) {}

    verify(token: string, ignoreExpiration = false): VerifyResult {
        try {
            const decoded = lib.verify(token, this.publicKey, { ignoreExpiration });
            return decoded ? VerifyResult.Valid : VerifyResult.Invalid;
        } catch (e) {
            if (e instanceof lib.ExpiredError) {
                return VerifyResult.Expired;
            }
            return VerifyResult.Invalid;
        }
    }

    verifyAsync(token: string, ignoreExpiration = false): Promise<VerifyResult> {
        return new Promise((resolve) => {
            lib.verify(
                token,
                this.publicKey,
                { ignoreExpiration },
                (err, decoded) => {
                    if (err) {
                        resolve(err instanceof lib.ExpiredError ? VerifyResult.Expired : VerifyResult.Invalid);
                        return;
                    }
                    resolve(decoded ? VerifyResult.Valid : VerifyResult.Invalid);
                },
            );
        });
    }

    extract(token: string): { payload?: unknown; status: VerifyResult } {
        try {
            const decoded = lib.verify(token, this.publicKey);
            return { payload: decoded, status: VerifyResult.Valid };
        } catch (e) {
            return { status: VerifyResult.Invalid };
        }
    }
}
