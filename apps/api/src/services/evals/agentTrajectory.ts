import { z } from 'zod';
import { metricEvaluationSchema, type MetricEvaluation } from './types.js';

export const trajectoryEvaluationSchema = z.object({
  argumentPrecision: metricEvaluationSchema.describe(
    'Mede a precisão e limpeza dos parâmetros passados para as ferramentas (ausência de ruídos e queries poluídas)'
  ),
  stepEfficiency: metricEvaluationSchema.describe(
    'Mede a eficiência do agente no uso do orçamento de passos e ausência de chamadas redundantes'
  ),
  overallScore: z.number().min(0).max(1).describe('Nota geral da trajetória do agente'),
});

export type TrajectoryEvaluation = z.infer<typeof trajectoryEvaluationSchema>;

export interface TrajectoryToolCall {
  toolName: string;
  args: Record<string, unknown>;
}

export interface TrajectoryStep {
  stepNumber: number;
  toolCalls: TrajectoryToolCall[];
}

export interface AgentTrajectoryTrace {
  userGoal: string;
  steps: TrajectoryStep[];
  totalSteps: number;
  redundantCalls?: number;
}

const NOISY_QUERY_PATTERNS = [
  /\b(guia completo|passo a passo|como pegar|detalhad|lendari|tutorial|trofeu de|troféu de|bronze|prata|ouro|platina)\b/i,
];

export function evaluateAgentTrajectory(trace: AgentTrajectoryTrace): TrajectoryEvaluation {
  const allToolCalls: TrajectoryToolCall[] = trace.steps.flatMap((s) => s.toolCalls);

  // 1. Argument Precision Evaluation
  let argScore = 1.0;
  const argDeductions: string[] = [];

  for (const call of allToolCalls) {
    if (call.toolName === 'search_trophy_guides') {
      const query = typeof call.args.query === 'string' ? call.args.query : '';
      const wordCount = query.trim().split(/\s+/).filter(Boolean).length;

      // Penalize excessively long queries in search_trophy_guides (should be clean trophy name)
      if (wordCount > 6) {
        argScore -= 0.4;
        argDeductions.push(`query excessivamente longa (${wordCount} palavras)`);
      }

      for (const pattern of NOISY_QUERY_PATTERNS) {
        if (pattern.test(query)) {
          argScore -= 0.3;
          argDeductions.push(`query poluída com termos de ruído ("${query}")`);
          break;
        }
      }
    }
  }

  const finalArgScore = Number(Math.max(0.0, Math.min(1.0, argScore)).toFixed(2));
  const argReasoning =
    argDeductions.length === 0
      ? 'Argumentos das ferramentas perfeitamente limpos e concisos.'
      : `Penalizações detectadas: ${argDeductions.join('; ')}.`;

  // 2. Step Efficiency Evaluation
  let efficiencyScore = 1.0;
  const efficiencyNotes: string[] = [];

  const redundantCount = trace.redundantCalls ?? 0;
  if (redundantCount > 0) {
    efficiencyScore -= redundantCount * 0.3;
    efficiencyNotes.push(`${redundantCount} chamada(s) redundante(s) detectada(s)`);
  }

  // 1 step is optimal for single-roundtrip prefetch
  if (trace.totalSteps === 1) {
    efficiencyNotes.push('Single roundtrip optimal execution.');
  } else if (trace.totalSteps > 3) {
    const excess = trace.totalSteps - 3;
    efficiencyScore -= excess * 0.15;
    efficiencyNotes.push(`execução em ${trace.totalSteps} passos (ideal <= 3)`);
  }

  const finalEfficiencyScore = Number(Math.max(0.0, Math.min(1.0, efficiencyScore)).toFixed(2));
  const efficiencyReasoning =
    efficiencyNotes.length === 0
      ? 'Execução eficiente e sem passos desperdiçados.'
      : efficiencyNotes.join('; ');

  const overall = Number(((finalArgScore * 0.5 + finalEfficiencyScore * 0.5)).toFixed(2));

  return {
    argumentPrecision: {
      score: finalArgScore,
      reasoning: argReasoning,
    },
    stepEfficiency: {
      score: finalEfficiencyScore,
      reasoning: efficiencyReasoning,
    },
    overallScore: overall,
  };
}
