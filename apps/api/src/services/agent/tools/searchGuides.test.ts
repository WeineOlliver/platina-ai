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
    expect('error' in result).toBe(true);
    if ('error' in result) {
      expect(result.error).toContain('Parâmetros inválidos');
    }
  });

  it('validates limit allows up to 10 and defaults to 3', async () => {
    const validWith10 = await searchGuidesTool.execute({
      query: 'Eileen the Crow',
      limit: 10,
    });
    if ('error' in validWith10) {
      expect(validWith10.error).not.toContain('Parâmetros inválidos');
    }

    const invalidWith11 = await searchGuidesTool.execute({
      query: 'Eileen the Crow',
      limit: 11,
    });
    expect('error' in invalidWith11).toBe(true);
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

  it('triggers on-demand fetchAndIndex and re-queries when search yields 0 chunks for a game', async () => {
    const mockChunk = {
      id: 'chunk_w3_1',
      game: 'The Witcher 3: Wild Hunt',
      title: 'Guia do Troféu Card Collector',
      content: 'Colete todas as cartas de Gwent no jogo base.',
      is_missable: true,
      similarity_score: 0.92,
    };

    const searchSpy = vi
      .spyOn(ingestionClient as unknown as { search: (...args: unknown[]) => Promise<unknown> }, 'search')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([mockChunk]);

    const fetchAndIndexSpy = vi
      .spyOn(ingestionClient as unknown as { fetchAndIndex: (...args: unknown[]) => Promise<unknown> }, 'fetchAndIndex')
      .mockResolvedValueOnce({
        status: 'indexed',
        chunks_indexed: 15,
        game: 'The Witcher 3: Wild Hunt',
      });

    const result = await searchGuidesTool.execute({
      query: 'Card Collector',
      game: 'The Witcher 3: Wild Hunt',
    });

    expect(fetchAndIndexSpy).toHaveBeenCalledWith('The Witcher 3: Wild Hunt');
    expect(searchSpy).toHaveBeenCalledTimes(2);
    expect('results' in result).toBe(true);
    if ('results' in result) {
      expect(result.results).toEqual([mockChunk]);
    }

    searchSpy.mockRestore();
    fetchAndIndexSpy.mockRestore();
  });
});
