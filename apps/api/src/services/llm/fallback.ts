export const DEFAULT_MODEL_CASCADE = [
  'openai/gpt-oss-120b',
  'openai/gpt-oss-20b',
  'qwen/qwen3.8-27b',
];

// Insight: Configurable LLM call timeout defaulting to 30 seconds
export const DEFAULT_LLM_TIMEOUT_MS = Number(process.env.LLM_TIMEOUT_MS) || 30000;

export interface CascadeOptions {
  timeoutMs?: number;
  logger?: { warn: (obj: unknown, msg: string) => void };
}

const isTransientError = (err: unknown): boolean => {
  if (!err) return false;
  const status = (err as { status?: number; statusCode?: number }).status ?? (err as { status?: number; statusCode?: number }).statusCode;
  const message = (err as { message?: string }).message;

  if (err instanceof Error) {
    if (err.name === 'TimeoutError' || err.name === 'AbortError') return true;
  }

  if (typeof status === 'number') {
    if (status === 401 || status === 403) return false;
    if (status === 429 || status >= 500 || status === 408) return true;
    if (status === 400 && typeof message === 'string') {
      const lower = message.toLowerCase();
      if (
        lower.includes('tool_use_failed') ||
        lower.includes('tool call validation failed') ||
        lower.includes('attempted to call tool')
      ) {
        return true;
      }
    }
    return false;
  }

  if (typeof message === 'string') {
    const lower = message.toLowerCase();
    if (
      lower.includes('rate limit reached') ||
      lower.includes('tokens per day') ||
      lower.includes('rate_limit_exceeded') ||
      lower.includes('tool_use_failed') ||
      lower.includes('tool call validation failed') ||
      lower.includes('attempted to call tool') ||
      lower.includes('timeout') ||
      lower.includes('timed out') ||
      lower.includes('abort') ||
      lower.includes('aborted') ||
      lower.includes('etimedout') ||
      lower.includes('tpd') ||
      lower.includes('tpm') ||
      lower.includes('rpm')
    ) {
      return true;
    }
  }

  return false;
};

export async function executeWithModelCascade<T>(
  models: string[],
  executeFn: (model: string) => Promise<T>,
  loggerOrOptions?: { warn: (obj: unknown, msg: string) => void } | CascadeOptions
): Promise<T> {
  if (!models.length) {
    throw new Error('No models provided in cascade list');
  }

  const options: CascadeOptions =
    loggerOrOptions && typeof (loggerOrOptions as { warn?: unknown }).warn === 'function'
      ? { logger: loggerOrOptions as { warn: (obj: unknown, msg: string) => void } }
      : (loggerOrOptions as CascadeOptions) ?? {};

  const timeoutMs = options.timeoutMs ?? DEFAULT_LLM_TIMEOUT_MS;
  const logger = options.logger;

  for (let i = 0; i < models.length; i++) {
    const model = models[i]!;
    try {
      // Insight: Timeout per LLM call (default 30s, configurable); cascades to next model on timeout
      let timer: NodeJS.Timeout | undefined;
      const timeoutPromise = new Promise<never>((_, reject) => {
        timer = setTimeout(() => {
          const err = new Error(`LLM call to model '${model}' timed out after ${timeoutMs}ms`);
          err.name = 'TimeoutError';
          reject(err);
        }, timeoutMs);
      });

      try {
        return await Promise.race([executeFn(model), timeoutPromise]);
      } finally {
        if (timer) clearTimeout(timer);
      }
    } catch (error: unknown) {
      const isLastModel = i === models.length - 1;

      if (isLastModel || !isTransientError(error)) {
        throw error;
      }

      const nextModel = models[i + 1]!;
      logger?.warn({ err: error, from: model, to: nextModel }, `Falling back from ${model} to ${nextModel}`);
    }
  }

  throw new Error('Exhausted all cascade models');
}
