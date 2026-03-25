/**
 * Exercises async generator methods, top-level generator functions,
 * exported generator functions, and generator function expressions
 * passed as call arguments.
 */

// --- top-level generator function (not exported) ---

async function* produce(source: Source): AsyncGenerator<Event, Summary> {
    for await (const item of source) {
        yield { type: 'item', value: item };
    }
    return { total: 0 };
}

// --- exported generator function ---

export async function* stream(config: Config): AsyncGenerator<Event, Summary> {
    const iter = config.source();
    const pieces = yield* dispatch(iter, async function*(msg) {
        if (msg.type === 'data') {
            yield { type: 'content', value: msg.value };
        }
        return msg.type === 'done' ? 'done' : undefined;
    });
    return buildSummary(pieces);
}

// --- result matcher with object-literal arrow values ---

export function matchResult<T>(result: Result<T>) {
    return match(result, {
        ok: (value) => value,
        err: () => undefined,
    });
}

// --- immediately-invoked generator wrapped in parens ---

export function buildStream(source: Source): AsyncGenerator<Event> {
    return (async function* () {
        for await (const item of source) {
            yield { type: 'item', value: item };
        }
    })();
}

// --- class with generator methods ---

export class EventProcessor {
    constructor(private readonly config: Config) {}

    async *process(input: string): AsyncGenerator<Event> {
        yield { type: 'start' };
        for await (const chunk of this.source(input)) {
            if (chunk.type === 'data') {
                yield* this.handleData(chunk);
            } else {
                yield* this.handleControl(chunk);
            }
        }
        yield { type: 'end' };
    }

    private async *handleData(chunk: DataChunk): AsyncGenerator<Event> {
        const result = await this.transform(chunk);
        yield { type: 'content', data: result };
    }

    private async *handleControl(chunk: ControlChunk): AsyncGenerator<Event> {
        yield { type: 'control', data: chunk.data };
    }

    status(): string {
        return 'running';
    }
}
