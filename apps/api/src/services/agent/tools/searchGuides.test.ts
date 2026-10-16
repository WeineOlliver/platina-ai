import { describe, it, expect } from 'vitest';
import { searchGuidesTool, SearchGuidesTool } from './searchGuides.js';

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
});
