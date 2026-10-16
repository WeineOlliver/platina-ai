export interface RetryOptions {
  maxRetries?: number;
  initialDelayMs?: number;
  maxDelayMs?: number;
  backoffFactor?: number;
  shouldRetry?: (error: unknown) => boolean;
}

// Insight: Exponential backoff with jitter prevents the "Thundering Herd" problem,
// where dozens of concurrent requests retry simultaneously and overwhelm an already rate-limited API.
export async function withRetry<T>(
  operation: (attempt: number) => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const maxRetries = options.maxRetries ?? 3;
  const initialDelayMs = options.initialDelayMs ?? 500;
  const maxDelayMs = options.maxDelayMs ?? 5000;
  const backoffFactor = options.backoffFactor ?? 2;

  let attempt = 0;
  let delay = initialDelayMs;

  while (true) {
    try {
      attempt++;
      return await operation(attempt);
    } catch (error: unknown) {
      const isLastAttempt = attempt > maxRetries;
      const canRetry = options.shouldRetry ? options.shouldRetry(error) : isRetryableError(error);

      if (isLastAttempt || !canRetry) {
        throw error;
      }

      // Add jitter: randomize between 80% and 120% of the computed delay
      const jitter = delay * (0.8 + Math.random() * 0.4);
      await new Promise((resolve) => setTimeout(resolve, jitter));

      // Calculate next backoff delay capped at maxDelayMs
      delay = Math.min(delay * backoffFactor, maxDelayMs);
    }
  }
}

/**
 * Determines if an error from an LLM API or network call is transient and safe to retry.
 */
export function isRetryableError(error: unknown): boolean {
  if (!error) return false;

  // Groq / OpenAI SDK errors often carry `status` or `statusCode`
  const status = (error as { status?: number; statusCode?: number }).status ??
                 (error as { status?: number; statusCode?: number }).statusCode;

  if (typeof status === 'number') {
    // 429 = Rate Limit Exceeded
    // 500, 502, 503, 504 = Transient upstream server errors
    if (status === 429 || (status >= 500 && status <= 504)) {
      return true;
    }
    // 400, 401, 403, 404 are client / authentication errors — retrying will NEVER succeed
    return false;
  }

  // Network / Node.js level errors (ECONNRESET, ETIMEDOUT, fetch failed)
  const code = (error as { code?: string }).code;
  if (code && ['ECONNRESET', 'ETIMEDOUT', 'ECONNREFUSED', 'EAI_AGAIN'].includes(code)) {
    return true;
  }

  const message = (error as { message?: string }).message?.toLowerCase() ?? '';
  if (message.includes('rate limit') || message.includes('timeout') || message.includes('overloaded')) {
    return true;
  }

  return false;
}
