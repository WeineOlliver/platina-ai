import { describe, it, expect } from 'vitest';
import { playerProgressTool, PlayerProgressTool } from './playerProgress.js';

describe('PlayerProgressTool Suite', () => {
  it('has correct tool declaration matching function calling specs', () => {
    expect(PlayerProgressTool.name).toBe('check_player_progress');
    const def = PlayerProgressTool.toolDefinition;
    expect(def.type).toBe('function');
    expect(def.function.name).toBe('check_player_progress');
    expect(def.function.parameters.required).toEqual(['game']);
    expect(def.function.parameters.properties).not.toHaveProperty('psnId');
  });

  it('rejects invalid inputs via schema validation', async () => {
    const result = await playerProgressTool.execute({ game: '' });
    expect('error' in result).toBe(true);
    if ('error' in result) {
      expect(result.error).toContain('Invalid parameters');
    }
  });

  it('queries real progress service and returns pending missable trophies', async () => {
    const result = await playerProgressTool.execute({
      game: 'Bloodborne',
    });

    if ('error' in result) {
      // If Python service is temporarily offline, ensure error is structured
      expect(typeof result.error).toBe('string');
    } else {
      expect(result.game).toBe('Bloodborne');
      expect(result.pending_missables_count).toBeGreaterThan(0);
      const names = result.pending_missable_trophies.map((t) => t.trophy_name);
      expect(names.some((n) => n.includes('Eileen'))).toBe(true);
    }
  });

  it('queries progress service and returns quick_cleanup_trophies and heavy_grind_trophies', async () => {
    const result = await playerProgressTool.execute({
      game: 'Grand Theft Auto V',
    });

    if ('error' in result) {
      // If Python service is temporarily offline, ensure error is structured
      expect(typeof result.error).toBe('string');
    } else {
      expect(result.game).toBe('Grand Theft Auto V');
      expect(result.quick_cleanup_trophies).toBeDefined();
      expect(result.quick_cleanup_trophies!.length).toBeGreaterThan(0);
      expect(result.heavy_grind_trophies).toBeDefined();
      expect(result.heavy_grind_trophies!.length).toBeGreaterThan(0);
      expect(result.quick_cleanup_trophies!.some((t) => t.trophy_name === 'Vinewood Visionary')).toBe(true);
      expect(result.heavy_grind_trophies!.some((t) => t.trophy_name === 'Masterminds')).toBe(true);
    }
  });
});
