export interface ApiResponse<T> {
    ok: boolean;
    data: T;
}

export type UserRecord = {
    id: number;
    name: string;
    email: string;
};

export type Handler<Name extends string, Payload> = {
    name: Name;
    run: (payload: Payload) => Promise<void>;
};
