import { describe, it, expect, vi } from 'vitest';
import { executeWithModelCascade, DEFAULT_MODEL_CASCADE } from './fallback.js';

describe('Model Cascade Fallback Suite', () => {
  it('defines DEFAULT_MODEL_CASCADE with expected models in order', () => {
    expect(DEFAULT_MODEL_CASCADE).toEqual([
      'openai/gpt-oss-120b',
      'openai/gpt-oss-20b',
      'qwen/qwen3.8-27b',
    ]);
  });

  it('succeeds on first model without calling subsequent models', async () => {
    const executeFn = vi.fn().mockResolvedValue('success-result');
    const logger = { warn: vi.fn() };

    const result = await executeWithModelCascade(DEFAULT_MODEL_CASCADE, executeFn, logger);

    expect(result).toBe('success-result');
    expect(executeFn).toHaveBeenCalledTimes(1);
    expect(executeFn).toHaveBeenCalledWith(DEFAULT_MODEL_CASCADE[0]);
    expect(logger.warn).not.toHaveBeenCalled();
  });

  it('fails over from 1st model (429 Rate Limit) to 2nd model (200 OK)', async () => {
    const error429 = new Error('Rate limit reached');
    (error429 as { status?: number }).status = 429;

    const executeFn = vi
      .fn()
      .mockRejectedValueOnce(error429)
      .mockResolvedValueOnce('recovered-result');
    const logger = { warn: vi.fn() };

    const result = await executeWithModelCascade(DEFAULT_MODEL_CASCADE, executeFn, logger);

    expect(result).toBe('recovered-result');
    expect(executeFn).toHaveBeenCalledTimes(2);
    expect(executeFn).toHaveBeenNthCalledWith(1, DEFAULT_MODEL_CASCADE[0]);
    expect(executeFn).toHaveBeenNthCalledWith(2, DEFAULT_MODEL_CASCADE[1]);
    expect(logger.warn).toHaveBeenCalledTimes(1);
    expect(logger.warn).toHaveBeenCalledWith(
      expect.anything(),
      `Falling back from ${DEFAULT_MODEL_CASCADE[0]} to ${DEFAULT_MODEL_CASCADE[1]}`
    );
  });

  it('fails over on 500 server error', async () => {
    const error500 = new Error('Internal Server Error');
    (error500 as { status?: number }).status = 500;

    const executeFn = vi
      .fn()
      .mockRejectedValueOnce(error500)
      .mockResolvedValueOnce('recovered-result');
    const logger = { warn: vi.fn() };

    const result = await executeWithModelCascade(DEFAULT_MODEL_CASCADE, executeFn, logger);

    expect(result).toBe('recovered-result');
    expect(executeFn).toHaveBeenCalledTimes(2);
  });

  it('fails over when error message contains rate limit keywords even without status', async () => {
    const errorTokens = new Error('tokens per day limit exceeded');
    const executeFn = vi
      .fn()
      .mockRejectedValueOnce(errorTokens)
      .mockResolvedValueOnce('recovered-result');
    const logger = { warn: vi.fn() };

    const result = await executeWithModelCascade(DEFAULT_MODEL_CASCADE, executeFn, logger);

    expect(result).toBe('recovered-result');
    expect(executeFn).toHaveBeenCalledTimes(2);
  });

  it('throws on 400 Bad Request without calling 2nd model', async () => {
    const error400 = new Error('Bad Request: Invalid prompt format');
    (error400 as { status?: number }).status = 400;

    const executeFn = vi.fn().mockRejectedValue(error400);
    const logger = { warn: vi.fn() };

    await expect(
      executeWithModelCascade(DEFAULT_MODEL_CASCADE, executeFn, logger)
    ).rejects.toThrow('Bad Request: Invalid prompt format');

    expect(executeFn).toHaveBeenCalledTimes(1);
    expect(executeFn).toHaveBeenCalledWith(DEFAULT_MODEL_CASCADE[0]);
    expect(logger.warn).not.toHaveBeenCalled();
  });

  it('throws when all cascade models are exhausted', async () => {
    const error429 = new Error('Rate limit exceeded: rate_limit_exceeded');
    (error429 as { status?: number }).status = 429;

    const executeFn = vi.fn().mockRejectedValue(error429);
    const logger = { warn: vi.fn() };

    await expect(
      executeWithModelCascade(DEFAULT_MODEL_CASCADE, executeFn, logger)
    ).rejects.toThrow('Rate limit exceeded: rate_limit_exceeded');

    expect(executeFn).toHaveBeenCalledTimes(DEFAULT_MODEL_CASCADE.length);
    expect(logger.warn).toHaveBeenCalledTimes(DEFAULT_MODEL_CASCADE.length - 1);
  });

  it('cascades to next model when 1st model times out (slow mock test)', async () => {
    // Insight: Slow mock test — 1st model exceeds timeoutMs (configurable), falling back to 2nd model
    const slowMock = vi.fn().mockImplementation((model: string) => {
      if (model === DEFAULT_MODEL_CASCADE[0]) {
        return new Promise((resolve) => setTimeout(() => resolve('slow-response'), 100));
      }
      return Promise.resolve('fast-fallback-response');
    });

    const logger = { warn: vi.fn() };
    const result = await executeWithModelCascade(DEFAULT_MODEL_CASCADE, slowMock, {
      timeoutMs: 25,
      logger,
    });

    expect(result).toBe('fast-fallback-response');
    expect(slowMock).toHaveBeenCalledTimes(2);
    expect(logger.warn).toHaveBeenCalledWith(
      expect.objectContaining({
        from: DEFAULT_MODEL_CASCADE[0],
        to: DEFAULT_MODEL_CASCADE[1],
      }),
      `Falling back from ${DEFAULT_MODEL_CASCADE[0]} to ${DEFAULT_MODEL_CASCADE[1]}`
    );
  });
});
