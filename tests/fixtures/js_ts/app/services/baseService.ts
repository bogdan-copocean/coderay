export class BaseService {
    static serviceName = 'base';

    processPayload(payload: Record<string, unknown>): Record<string, unknown> {
        return { ...payload, processedBy: BaseService.serviceName };
    }
}
