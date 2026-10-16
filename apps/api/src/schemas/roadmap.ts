import { z } from 'zod';

// Contrato de entrada: o que o cliente envia
export const roadmapRequestSchema = z.object({
  game: z.string().min(2, 'O nome do jogo deve ter pelo menos 2 caracteres').max(100),
});

export type RoadmapRequest = z.infer<typeof roadmapRequestSchema>;

// Contrato de saída estruturada: o que o LLM DEVE devolver obrigatoriamente
export const missableTrophySchema = z.object({
  trophyName: z.string().describe('Nome do troféu'),
  chapterOrLocation: z.string().describe('Capítulo, missão ou região onde o troféu pode ser perdido'),
  missableReason: z.string().describe('Instrução exata do que o jogador não pode fazer para não perder o troféu'),
});

export const trophyRoadmapSchema = z.object({
  game: z.string().describe('Nome do jogo'),
  difficulty: z.number().min(1).max(10).describe('Dificuldade estimada para platina de 1 a 10'),
  estimatedHours: z.number().min(1).describe('Tempo estimado em horas para platinar'),
  minimumPlaythroughs: z.number().min(1).describe('Número mínimo de jogadas necessárias'),
  hasOnlineTrophies: z.boolean().describe('Se possui troféus multiplayer/online obrigatórios'),
  missables: z.array(missableTrophySchema).describe('Lista detalhada de troféus perdíveis'),
  recommendedRoute: z.array(z.string()).min(1).describe('Etapas recomendadas em ordem cronológica'),
});

export type MissableTrophy = z.infer<typeof missableTrophySchema>;
export type TrophyRoadmap = z.infer<typeof trophyRoadmapSchema>;
