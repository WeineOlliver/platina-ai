import { describe, it, expect, vi } from 'vitest';
import { withRetry, isRetryableError } from './retry.js';

describe('Retry Utility Suite', () => {
  it('returns result immediately on first successful attempt', async () => {
    const fn = vi.fn().mockResolvedValue('success');
    const result = await withRetry(fn);

    expect(result).toBe('success');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('retries on retryable error and succeeds on subsequent attempt', async () => {
    let callCount = 0;
    const fn = vi.fn(async () => {
      callCount++;
      if (callCount < 3) {
        const error = new Error('Rate limit exceeded');
        (error as { status?: number }).status = 429;
        throw error;
      }
      return 'recovered';
    });

    const result = await withRetry(fn, {
      maxRetries: 3,
      initialDelayMs: 10,
      maxDelayMs: 50,
    });

    expect(result).toBe('recovered');
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it('does not retry on fatal client error (e.g. 400 Bad Request)', async () => {
    const fn = vi.fn(async () => {
      const error = new Error('Bad Request');
      (error as { status?: number }).status = 400;
      throw error;
    });

    await expect(withRetry(fn, { maxRetries: 3, initialDelayMs: 10 })).rejects.toThrow('Bad Request');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('isRetryableError correctly identifies 429 and 503', () => {
    expect(isRetryableError({ status: 429 })).toBe(true);
    expect(isRetryableError({ status: 503 })).toBe(true);
    expect(isRetryableError({ status: 400 })).toBe(false);
    expect(isRetryableError({ status: 401 })).toBe(false);
  });
});
