import { z } from 'zod';

export const metricEvaluationSchema = z.object({
  score: z.number().min(0).max(1).describe('Nota contínua entre 0.0 e 1.0 atribuída pelo juiz'),
  reasoning: z.string().min(1).describe('Justificativa técnica detalhada para a pontuação'),
});

export type MetricEvaluation = z.infer<typeof metricEvaluationSchema>;

export const ragTriadEvaluationSchema = z.object({
  contextRelevance: metricEvaluationSchema.describe(
    'Mede se os contextos recuperados contêm as informações necessárias para responder à pergunta'
  ),
  faithfulness: metricEvaluationSchema.describe(
    'Mede se cada afirmação da resposta é estritamente sustentada pelo contexto fornecido (anti-alucinação)'
  ),
  answerRelevance: metricEvaluationSchema.describe(
    'Mede se a resposta atende diretamente à pergunta original do usuário sem desvios'
  ),
  overallScore: z.number().min(0).max(1).describe('Média ponderada ou aritmética das 3 métricas da tríade'),
});

export type RagTriadEvaluation = z.infer<typeof ragTriadEvaluationSchema>;

export interface RagTriadInput {
  query: string;
  contexts: string[];
  answer: string;
}
