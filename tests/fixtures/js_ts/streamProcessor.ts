/**
 * Stream processor using async generators and yield* delegation.
 */

export class StreamProcessor {
    async *process(input: string): AsyncGenerator<Message> {
        yield { type: 'start' };

        for await (const chunk of this.source(input)) {
            if (chunk.type === 'data') {
                yield* this.handleData(chunk);
            } else if (chunk.type === 'control') {
                yield* this.handleControl(chunk);
            }
        }

        yield { type: 'end', reason: 'done' };
    }

    private async *handleData(chunk: DataChunk): AsyncGenerator<Message> {
        const result = await this.transform(chunk);
        yield { type: 'content', content: result };
    }

    private async *handleControl(
        chunk: ControlChunk,
    ): AsyncGenerator<Message> {
        yield { type: 'control', data: chunk.data };
    }
}
