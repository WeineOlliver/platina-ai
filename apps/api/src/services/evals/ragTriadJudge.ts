import Groq from 'groq-sdk';
import { env } from '../../config/env.js';
import { executeWithModelCascade, DEFAULT_MODEL_CASCADE } from '../llm/fallback.js';
import {
  type RagTriadInput,
  type RagTriadEvaluation,
  ragTriadEvaluationSchema,
} from './types.js';

export * from './types.js';

const RAG_TRIAD_JUDGE_SYSTEM_PROMPT = `Você é um avaliador rigoroso e imparcial de sistemas RAG (Retrieval-Augmented Generation), especializado no framework RAG Triad.
Sua tarefa é analisar a pergunta do usuário, os contextos recuperados e a resposta gerada, pontuando cada dimensão de 0.0 a 1.0 com justificativa concisa.

As 3 dimensões obrigatórias:
1. Context Relevance (0.0 a 1.0):
   - Os trechos recuperados contêm fatos úteis e pertinentes para responder à dúvida?
   - Dê nota baixa (< 0.4) se os contextos tratarem de outros jogos, assuntos irrelevantes ou puro ruído.

2. Faithfulness / Groundedness (0.0 a 1.0):
   - Cada alegação, instrução ou entidade na resposta é diretamente comprovada pelos contextos?
   - Dê nota alta (0.8 - 1.0) se a resposta não trouxer NENHUM fato inventado.
   - Dê nota baixa (< 0.4) se a resposta contiver alucinações, nomes de chefes, locais ou regras que NÃO estão no contexto.
   - Se o contexto for vazio ou insuficiente e a resposta honestamente admitir isso, a fidelidade é 1.0.

3. Answer Relevance (0.0 a 1.0):
   - A resposta responde diretamente ao que o usuário perguntou?
   - Dê nota baixa (< 0.4) se o texto fugir do tema ou ignorar o objetivo do jogador.

4. Tratamento Especial para Ausência de Contexto / Jogo Desconhecido:
   - Se o contexto for vazio ou não contiver o guia do jogo e a resposta admitir honestamente isso (ex: "Guia oficial não encontrado para este objetivo. Quer que eu procure em fontes complementares?"), atribua Context Relevance = 0.0 (não havia contexto), Faithfulness = 1.0 (não alucinou nenhum fato falso) e Answer Relevance = 0.8 (comunicou o status correto e ofereceu proativamente o próximo passo).

Formato de saída:
Responda EXCLUSIVAMENTE um objeto JSON válido correspondente ao schema:
{
  "contextRelevance": { "score": 0.9, "reasoning": "..." },
  "faithfulness": { "score": 0.9, "reasoning": "..." },
  "answerRelevance": { "score": 0.9, "reasoning": "..." },
  "overallScore": 0.9
}`;

function evaluateDeterministically(input: RagTriadInput): RagTriadEvaluation {
  const queryLower = input.query.toLowerCase();
  const answerLower = input.answer.toLowerCase();
  const fullContext = input.contexts.join(' ').toLowerCase();

  const isHonestAdmission =
    /não foi possível encontrar|guia oficial não encontrado|quer que eu procure/i.test(input.answer);

  // 1. Context Relevance
  let contextScore: number;
  if (input.contexts.length === 0) {
    contextScore = isHonestAdmission ? 1.0 : 0.0;
  } else {
    const queryTokens = queryLower.split(/\W+/).filter((t) => t.length > 3);
    const matchingContextTokens = queryTokens.filter((t) => fullContext.includes(t));
    const contextRatio = queryTokens.length ? matchingContextTokens.length / queryTokens.length : 1;
    contextScore = Number(contextRatio.toFixed(2));
  }

  // 2. Faithfulness
  let faithfulnessScore: number;
  if (isHonestAdmission) {
    faithfulnessScore = 1.0;
  } else {
    const answerTokens = answerLower.split(/\W+/).filter((t) => t.length > 3);
    const stopwords = new Set([
      'para', 'como', 'onde', 'este', 'esta', 'você', 'voce', 'troféu', 'trofeu',
      'antes', 'depois', 'obter', 'coletar', 'guia', 'quer', 'detalhes', 'completos',
      'rotas', 'deste'
    ]);
    const relevantAnswerTokens = answerTokens.filter((t) => !stopwords.has(t));
    const groundedTokens = relevantAnswerTokens.filter((t) => fullContext.includes(t));
    const faithRatio = relevantAnswerTokens.length ? groundedTokens.length / relevantAnswerTokens.length : 1;
    faithfulnessScore = Number(faithRatio.toFixed(2));
  }

  // 3. Answer Relevance
  let answerRelevanceScore: number;
  if (isHonestAdmission) {
    answerRelevanceScore = 0.85;
  } else {
    const queryTokens = queryLower.split(/\W+/).filter((t) => t.length > 3);
    const matchingAnswerTokens = queryTokens.filter((t) => answerLower.includes(t));
    const answerRatio = queryTokens.length ? matchingAnswerTokens.length / queryTokens.length : 1;
    answerRelevanceScore = Number(answerRatio.toFixed(2));
  }

  const overall = Number(((contextScore + faithfulnessScore + answerRelevanceScore) / 3).toFixed(2));

  return {
    contextRelevance: {
      score: contextScore,
      reasoning: `Relevância do contexto calculada em ${Math.round(contextScore * 100)}% de cobertura de termos da pergunta.`,
    },
    faithfulness: {
      score: faithfulnessScore,
      reasoning: `Fidelidade calculada em ${Math.round(faithfulnessScore * 100)}% de sustentação das alegações no contexto.`,
    },
    answerRelevance: {
      score: answerRelevanceScore,
      reasoning: `Pertinência da resposta avaliada em ${Math.round(answerRelevanceScore * 100)}% de aderência ao objetivo do usuário.`,
    },
    overallScore: overall,
  };
}

export async function evaluateRagTriad(
  input: RagTriadInput,
  options: { groqClient?: Groq; model?: string; mock?: boolean } = {}
): Promise<RagTriadEvaluation> {
  const apiKey = env.GROQ_API_KEY;
  const isMock = options.mock || env.AI_PROVIDER === 'mock' || !apiKey;

  if (isMock && !options.groqClient) {
    return evaluateDeterministically(input);
  }

  const client = options.groqClient || new Groq({ apiKey });
  const cascadeModels = [
    options.model || env.GROQ_MODEL,
    ...DEFAULT_MODEL_CASCADE.filter((m) => m !== (options.model || env.GROQ_MODEL)),
  ];

  const userPrompt = `<pergunta_usuario>
${input.query}
</pergunta_usuario>

<contextos_recuperados>
${input.contexts.map((c, i) => `[Contexto ${i + 1}]:\n${c}`).join('\n\n')}
</contextos_recuperados>

<resposta_agente>
${input.answer}
</resposta_agente>`;

  try {
    const completion = await executeWithModelCascade(cascadeModels, (model) =>
      client.chat.completions.create({
        model,
        messages: [
          { role: 'system', content: RAG_TRIAD_JUDGE_SYSTEM_PROMPT },
          { role: 'user', content: userPrompt },
        ],
        response_format: { type: 'json_object' },
        temperature: 0.1,
        max_tokens: model.includes('qwen') ? 600 : 800,
      })
    );

    const rawJson = completion.choices[0]?.message?.content || '{}';
    const parsed = JSON.parse(rawJson);
    const validation = ragTriadEvaluationSchema.safeParse(parsed);

    if (validation.success) {
      return validation.data;
    }
    console.warn('⚠️ RAG Triad Judge JSON validation error, falling back to deterministic evaluation:', validation.error.format());
  } catch (err) {
    console.warn('⚠️ RAG Triad Judge LLM call failed, falling back to deterministic evaluation:', err);
  }

  return evaluateDeterministically(input);
}
