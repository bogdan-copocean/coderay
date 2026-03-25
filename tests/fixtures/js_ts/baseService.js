/**
 * Base service - for extends/inheritance tests.
 */

export class BaseService {
    constructor() {
        this.initialized = true;
    }

    init() {
        return this.initialized;
    }
}
