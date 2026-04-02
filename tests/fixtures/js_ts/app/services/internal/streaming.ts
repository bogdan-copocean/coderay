type Chunk = { type: 'data' | 'control'; value: string };
type Message = { type: 'content' | 'control'; value: string };

export class StreamProcessor {
    async *process(chunks: AsyncIterable<Chunk>): AsyncGenerator<Message> {
        for await (const chunk of chunks) {
            if (chunk.type === 'data') {
                yield* this.handleData(chunk);
            } else {
                yield* this.handleControl(chunk);
            }
        }
    }

    private async *handleData(chunk: Chunk): AsyncGenerator<Message> {
        yield { type: 'content', value: chunk.value.toUpperCase() };
    }

    private async *handleControl(chunk: Chunk): AsyncGenerator<Message> {
        yield { type: 'control', value: chunk.value };
    }
}
