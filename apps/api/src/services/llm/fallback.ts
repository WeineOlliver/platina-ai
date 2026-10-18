export const DEFAULT_MODEL_CASCADE = [
  'openai/gpt-oss-120b',
  'openai/gpt-oss-20b',
  'qwen/qwen3.8-27b',
];

function isTransientError(error: unknown): boolean {
  if (!error) return false;

  const status =
    (error as { status?: number; statusCode?: number }).status ??
    (error as { status?: number; statusCode?: number }).statusCode;

  if (typeof status === 'number') {
    if (status === 400 || status === 401 || status === 403) {
      return false;
    }
    if (status === 429 || status >= 500) {
      return true;
    }
    return false;
  }

  const message = (error as { message?: string }).message;
  if (typeof message === 'string') {
    const lower = message.toLowerCase();
    if (
      lower.includes('rate limit reached') ||
      lower.includes('tokens per day') ||
      lower.includes('rate_limit_exceeded')
    ) {
      return true;
    }
  }

  return false;
}

export async function executeWithModelCascade<T>(
  models: string[],
  executeFn: (model: string) => Promise<T>,
  logger?: { warn: (obj: unknown, msg: string) => void }
): Promise<T> {
  if (!models.length) {
    throw new Error('No models provided in cascade list');
  }

  for (let i = 0; i < models.length; i++) {
    const model = models[i]!;
    try {
      return await executeFn(model);
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
