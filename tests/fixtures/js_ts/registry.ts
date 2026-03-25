/**
 * Registry module with module-scope helpers and a class with static factory methods.
 */

type HandlerOptions = {
    timeout: number;
};

type Handler<Name extends string> = {
    name: Name;
    execute: () => Promise<void>;
};

const ALL_HANDLERS = defineHandlers({
    ping: PingHandler,
    fetch: FetchHandler,
    retry: RetryHandler,
});

export class Registry {
    static forRoot(): Registry {
        return new Registry(Object.values(ALL_HANDLERS));
    }

    static forTesting({ overrides }: { overrides: Record<string, unknown> }): Registry {
        return new Registry([]);
    }
}

function defineHandlers<const T extends Record<string, unknown>>(handlers: T): T {
    return handlers;
}

function getToken(name: string): symbol {
    return Symbol(name);
}
