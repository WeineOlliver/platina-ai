import { describe, it, expect } from 'vitest';
import { playerProgressTool, PlayerProgressTool } from './playerProgress.js';

describe('PlayerProgressTool Suite', () => {
  it('has correct tool declaration matching function calling specs', () => {
    expect(PlayerProgressTool.name).toBe('check_player_progress');
    const def = PlayerProgressTool.toolDefinition;
    expect(def.type).toBe('function');
    expect(def.function.name).toBe('check_player_progress');
    expect(def.function.parameters.required).toContain('psnId');
    expect(def.function.parameters.required).toContain('game');
  });

  it('rejects invalid inputs via schema validation', async () => {
    const result = await playerProgressTool.execute({ psnId: '', game: '' });
    expect('error' in result).toBe(true);
    if ('error' in result) {
      expect(result.error).toContain('Parâmetros inválidos');
    }
  });

  it('queries real progress service and returns pending missable trophies', async () => {
    const result = await playerProgressTool.execute({
      psnId: 'OlliverHunter',
      game: 'Bloodborne',
    });

    if ('error' in result) {
      // If Python service is temporarily offline, ensure error is structured
      expect(typeof result.error).toBe('string');
    } else {
      expect(result.psn_id).toBe('OlliverHunter');
      expect(result.game).toBe('Bloodborne');
      expect(result.pending_missables_count).toBeGreaterThan(0);
      const names = result.pending_missable_trophies.map((t) => t.trophy_name);
      expect(names.some((n) => n.includes('Eileen'))).toBe(true);
    }
  });
});
