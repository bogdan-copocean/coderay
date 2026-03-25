/**
 * Service with callback-heavy methods — exercises Promise and nested callback patterns.
 */

export class TaskRunner {
    constructor(private readonly config: RunnerConfig) {}

    run(task: Task, options: RunOptions = {}): RunResult {
        try {
            const output = lib.execute(task, this.config, options);
            return output ? RunResult.Success : RunResult.Failed;
        } catch (e) {
            if (e instanceof lib.TimeoutError) {
                return RunResult.TimedOut;
            }
            return RunResult.Failed;
        }
    }

    runAsync(task: Task, options: RunOptions = {}): Promise<RunResult> {
        return new Promise((resolve) => {
            lib.execute(
                task,
                this.config,
                options,
                (err, output) => {
                    if (err) {
                        resolve(err instanceof lib.TimeoutError ? RunResult.TimedOut : RunResult.Failed);
                        return;
                    }
                    resolve(output ? RunResult.Success : RunResult.Failed);
                },
            );
        });
    }

    inspect(task: Task): { output?: unknown; status: RunResult } {
        try {
            const output = lib.execute(task, this.config);
            return { output, status: RunResult.Success };
        } catch (e) {
            return { status: RunResult.Failed };
        }
    }
}
