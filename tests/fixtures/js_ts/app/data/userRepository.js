export class UserRepository {
    constructor() {
        this.records = new Map([
            [1, { id: 1, name: 'Ada', email: 'ada@example.com' }],
            [2, { id: 2, name: 'Linus', email: 'linus@example.com' }],
        ]);
    }

    findById(id) {
        return this.records.get(id);
    }
}
