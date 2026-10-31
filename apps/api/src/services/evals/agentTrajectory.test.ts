import { describe, it, expect } from 'vitest';
import {
  evaluateAgentTrajectory,
  type AgentTrajectoryTrace,
  type TrajectoryEvaluation,
} from './agentTrajectory.js';

describe('Agent Trajectory & Tool Execution Evaluation Suite', () => {
  it('evaluates an optimal single-trophy search trajectory with high argument precision and efficiency', () => {
    const trace: AgentTrajectoryTrace = {
      userGoal: 'Como pegar o troféu Card Collector em The Witcher 3?',
      steps: [
        {
          stepNumber: 1,
          toolCalls: [
            {
              toolName: 'search_trophy_guides',
              args: { query: 'Card Collector', game: 'The Witcher 3' },
            },
          ],
        },
      ],
      totalSteps: 2, // 1 tool step + 1 final text synthesis
      redundantCalls: 0,
    };

    const evaluation: TrajectoryEvaluation = evaluateAgentTrajectory(trace);

    expect(evaluation.argumentPrecision.score).toBeGreaterThanOrEqual(0.9);
    expect(evaluation.stepEfficiency.score).toBeGreaterThanOrEqual(0.9);
    expect(evaluation.overallScore).toBeGreaterThanOrEqual(0.9);
    expect(evaluation.argumentPrecision.reasoning).toBeTruthy();
    expect(evaluation.stepEfficiency.reasoning).toBeTruthy();
  });

  it('penalizes argument precision when tool query contains noisy adjectives or descriptions', () => {
    const trace: AgentTrajectoryTrace = {
      userGoal: 'Como pegar a Lança de Gransax em Elden Ring?',
      steps: [
        {
          stepNumber: 1,
          toolCalls: [
            {
              toolName: 'search_trophy_guides',
              args: {
                query: 'guia completo e detalhado como pegar o trofeu de bronze ou prata da lendaria lança de gransax',
                game: 'Elden Ring',
              },
            },
          ],
        },
      ],
      totalSteps: 2,
      redundantCalls: 0,
    };

    const evaluation: TrajectoryEvaluation = evaluateAgentTrajectory(trace);

    // Argument precision should be heavily penalized for concatenating long instructions and words like bronze/prata/guia
    expect(evaluation.argumentPrecision.score).toBeLessThanOrEqual(0.4);
    expect(evaluation.argumentPrecision.reasoning).toContain('poluída');
  });

  it('penalizes step efficiency when the agent makes redundant tool calls or takes excessive steps', () => {
    const trace: AgentTrajectoryTrace = {
      userGoal: 'Qual meu progresso no GTA V?',
      steps: [
        {
          stepNumber: 1,
          toolCalls: [
            {
              toolName: 'get_trophy_guide',
              args: { game: 'Grand Theft Auto V', trophy: 'San Andreas Sightseer' },
            },
          ],
        },
        {
          stepNumber: 2,
          toolCalls: [
            {
              toolName: 'get_trophy_guide',
              args: { game: 'Grand Theft Auto V', trophy: 'San Andreas Sightseer' },
            },
          ],
        },
        {
          stepNumber: 3,
          toolCalls: [
            {
              toolName: 'search_trophy_guides',
              args: { query: 'geral', game: 'Grand Theft Auto V' },
            },
          ],
        },
        {
          stepNumber: 4,
          toolCalls: [
            {
              toolName: 'search_trophy_guides',
              args: { query: 'geral', game: 'Grand Theft Auto V' },
            },
          ],
        },
      ],
      totalSteps: 5,
      redundantCalls: 2,
    };

    const evaluation: TrajectoryEvaluation = evaluateAgentTrajectory(trace);

    expect(evaluation.stepEfficiency.score).toBeLessThanOrEqual(0.4);
    expect(evaluation.stepEfficiency.reasoning).toContain('redundante');
  });

  it('awards maximum efficiency score when onboarding prefetch resolves in a single roundtrip (1 step)', () => {
    const trace: AgentTrajectoryTrace = {
      userGoal: 'Olá, sou OlliverHunter jogando GTA V',
      steps: [], // zero in-loop tool calls because it was prefetched
      totalSteps: 1, // generated directly in single roundtrip
      redundantCalls: 0,
    };

    const evaluation: TrajectoryEvaluation = evaluateAgentTrajectory(trace);

    expect(evaluation.stepEfficiency.score).toBe(1.0);
    expect(evaluation.stepEfficiency.reasoning).toContain('Single roundtrip');
  });
});
