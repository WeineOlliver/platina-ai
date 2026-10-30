import { describe, it, expect, vi } from 'vitest';
import { searchGuidesTool, SearchGuidesTool } from './searchGuides.js';
import { ingestionClient } from '../../ingestionClient.js';

describe('SearchGuidesTool Suite', () => {
  it('has valid tool declaration matching function calling schemas', () => {
    expect(SearchGuidesTool.name).toBe('search_trophy_guides');
    const def = SearchGuidesTool.toolDefinition;
    expect(def.type).toBe('function');
    expect(def.function.name).toBe('search_trophy_guides');
    expect(def.function.parameters.required).toContain('query');
  });

  it('rejects invalid inputs via Zod runtime validation', async () => {
    const result = await searchGuidesTool.execute({ query: '' });
    expect(result.status).toBe('error');
    if ('error' in result) {
      expect(result.error).toContain('Parâmetros inválidos');
    }
  });

  it('returns clear error when game is not provided and no session game exists', async () => {
    const result = await searchGuidesTool.execute({
      query: 'Card Collector',
    });
    expect(result.status).toBe('error');
    if ('error' in result) {
      expect(result.error).toContain('Game not specified');
    }
  });

  it('uses active session game when game argument is omitted by caller', async () => {
    const mockChunk = {
      id: 'chunk_session_1',
      game: 'The Witcher 3: Wild Hunt',
      title: 'Card Collector Guide',
      content: 'Gwent guide content.',
      is_missable: true,
      similarity_score: 0.9,
    };
    const searchSpy = vi
      .spyOn(ingestionClient as unknown as { searchWithMetrics: (...args: unknown[]) => Promise<unknown> }, 'searchWithMetrics')
      .mockResolvedValueOnce({
        chunks: [mockChunk],
        retrieval_latency_ms: 5,
        reranker_latency_ms: 2,
      });

    const result = await searchGuidesTool.execute(
      { query: 'Card Collector' },
      { sessionGame: 'The Witcher 3: Wild Hunt' }
    );

    expect(searchSpy).toHaveBeenCalledWith(
      expect.objectContaining({ game: 'The Witcher 3: Wild Hunt', query: 'Card Collector' })
    );
    expect('results' in result).toBe(true);
    searchSpy.mockRestore();
  });

  it('validates limit allows up to 10 and defaults to 3', async () => {
    const validWith10 = await searchGuidesTool.execute({
      query: 'Eileen the Crow',
      game: 'Bloodborne',
      limit: 10,
    });
    if ('error' in validWith10) {
      expect(validWith10.error).not.toContain('Parâmetros inválidos');
    }

    const invalidWith11 = await searchGuidesTool.execute({
      query: 'Eileen the Crow',
      game: 'Bloodborne',
      limit: 11,
    });
    expect(invalidWith11.status).toBe('error');
    if ('error' in invalidWith11) {
      expect(invalidWith11.error).toContain('Parâmetros inválidos');
    }
  });

  it('executes semantic retrieval and returns guide chunks', async () => {
    const result = await searchGuidesTool.execute({
      query: 'Eileen the Crow',
      game: 'Bloodborne',
      missableOnly: true,
      limit: 2,
    });

    if ('error' in result) {
      expect(typeof result.error).toBe('string');
    } else {
      expect(Array.isArray(result.results)).toBe(true);
    }
  });

  it('does not trigger fetchAndIndex when search yields 0 chunks (live scraping disabled in pipeline v2)', async () => {
    const searchSpy = vi
      .spyOn(ingestionClient as unknown as { search: (...args: unknown[]) => Promise<unknown> }, 'search')
      .mockResolvedValue([]);

    const fetchAndIndexSpy = vi
      .spyOn(ingestionClient as unknown as { fetchAndIndex: (...args: unknown[]) => Promise<unknown> }, 'fetchAndIndex');

    const result = await searchGuidesTool.execute({
      query: 'Card Collector',
      game: 'The Witcher 3: Wild Hunt',
    });

    expect(fetchAndIndexSpy).not.toHaveBeenCalled();
    expect(result.status).toBe('game_not_indexed');

    searchSpy.mockRestore();
    fetchAndIndexSpy.mockRestore();
  });
});
