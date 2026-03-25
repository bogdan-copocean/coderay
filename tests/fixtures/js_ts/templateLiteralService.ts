/**
 * Exercises functions whose bodies contain template literals with embedded
 * newlines — a pattern that confused the signature-line extractor because
 * ":\n" inside the template literal was found before the body-opening "{".
 */

export async function* produce(
    source: Source,
    config: Config,
): AsyncGenerator<Event, void> {
    const header = `
        label: ${config.name}
        value: ${config.id}
    `;
    for await (const item of source) {
        yield { type: 'item', value: item, header };
    }
}

export class ReportBuilder {
    constructor(private readonly name: string) {}

    build(items: Item[]): string {
        const body = `
            title: ${this.name}
            count: ${items.length}
        `;
        return body.trim();
    }

    format(label: string, value: unknown): string {
        return `${label}: ${value}`;
    }
}
