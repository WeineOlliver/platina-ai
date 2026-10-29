// Insight: Bridge script to run complete PlatinaAgentRunner on hybrid and none eval cases
// and score results using ragTriadJudge for golden dataset evaluations.
import { PlatinaAgentRunner, type AgentStepEvent } from '../agent/runner.js';
import { evaluateRagTriad } from './ragTriadJudge.js';

interface TestCaseInput {
  id: string;
  category: string;
  route: string;
  question: string;
  game?: string;
  toolOnly?: boolean;
  expected?: {
    trophies?: string[];
    must_contain?: string[];
    must_contain_any?: string[];
    abstain?: boolean;
    note?: string;
  };
}

function normalizeStr(s: string): string {
  if (!s) return '';
  return s
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[’‘`]/g, "'")
    .replace(/…/g, '...')
    .replace(/[\u202f\u00a0]/g, ' ')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

async function main() {
  const inputRaw = process.argv[2];
  if (!inputRaw) {
    console.error(JSON.stringify({ error: 'Missing JSON input argument' }));
    process.exit(1);
  }

  const testCase: TestCaseInput = JSON.parse(inputRaw);
  const runner = new PlatinaAgentRunner();

  const collectedContexts: string[] = [];
  interface CapturedToolCall {
    name: string;
    args: unknown;
    status: string;
    returned_chunk_titles: string[];
  }
  const toolCalls: CapturedToolCall[] = [];
  let finalAnswer = '';

  try {
    for await (const event of runner.run(testCase.question, {
      game: testCase.game || 'The Witcher 3: Wild Hunt',
      lang: 'pt',
    })) {
      if (event.type === 'tool_call') {
        toolCalls.push({
          name: event.toolName || '',
          args: event.toolArgs,
          status: 'pending',
          returned_chunk_titles: [],
        });
        if (testCase.toolOnly) {
          // Immediately exit if caller only requested tool call translation probe
          break;
        }
      }
      if (event.type === 'tool_result' && event.toolResult) {
        const lastCall = toolCalls[toolCalls.length - 1];
        if (lastCall) {
          const tr = event.toolResult as {
            status?: string;
            error?: string;
            results?: Array<{ title?: string; content?: string }>;
          };
          if (tr.error) {
            lastCall.status = 'error';
          } else if (tr.status) {
            lastCall.status = tr.status;
          }
          if (Array.isArray(tr.results)) {
            lastCall.returned_chunk_titles = tr.results
              .map((c) => c.title || '')
              .filter(Boolean);
            if (!tr.status) {
              lastCall.status = lastCall.returned_chunk_titles.length > 0 ? 'success' : 'no_results';
            }
            for (const chunk of tr.results) {
              if (chunk.content) {
                collectedContexts.push(`[${chunk.title}]: ${chunk.content}`);
              }
            }
          }
        }
      }
      if (event.type === 'chunk' && event.content) {
        finalAnswer += event.content;
      }
    }

    if (testCase.toolOnly) {
      console.log('__EVAL_RESULT_START__' + JSON.stringify({
        id: testCase.id,
        category: testCase.category,
        route: testCase.route,
        question: testCase.question,
        status: 'PASSED',
        toolCalls,
        evaluation: null,
      }) + '__EVAL_RESULT_END__');
      process.exit(0);
    }

    // Insight: Empty answer or temporary failure from LLM must be classified as ERROR rather than logical FAILED
    const isTemporaryFailure =
      !finalAnswer.trim() ||
      /falha temporária no serviço|temporary service failure/i.test(finalAnswer);

    if (isTemporaryFailure) {
      console.log(
        '__EVAL_RESULT_START__' +
        JSON.stringify({
          id: testCase.id,
          category: testCase.category,
          route: testCase.route,
          question: testCase.question,
          status: 'ERROR',
          error: !finalAnswer.trim()
            ? 'Empty final response from agent'
            : 'Temporary service failure returned by agent',
          toolCalls,
          evaluation: null,
        }) +
        '__EVAL_RESULT_END__'
      );
      process.exit(0);
    }

    const evaluation = await evaluateRagTriad({
      query: testCase.question,
      contexts: collectedContexts,
      answer: finalAnswer,
    });

    const isAbstained =
      /não foi possível encontrar|guia oficial não encontrado|quer que eu procure|não encontrado|não existe|não possuo|não temos|desculpe|infelizmente|não está disponível|official guide not found/i.test(
        finalAnswer
      );

    let passed = false;
    const reasons: string[] = [];

    if (testCase.route === 'none') {
      // For 'none', criterion is strictly abstention
      passed = Boolean(isAbstained);
      if (!passed) {
        reasons.push('Agent failed to abstain and may have hallucinated facts');
      }
    } else if (testCase.route === 'hybrid') {
      // For 'hybrid', must mention expected trophies/must_contain and maintain high triad score (faithfulness >= 0.8)
      const expectedTrophies = testCase.expected?.trophies || [];
      const mustContain = testCase.expected?.must_contain || [];
      const mustContainAny = testCase.expected?.must_contain_any || [];

      const answerNorm = normalizeStr(finalAnswer);
      const missingTrophies = expectedTrophies.filter(
        (t) => !answerNorm.includes(normalizeStr(t))
      );
      const missingMustContain = mustContain.filter(
        (t) => !answerNorm.includes(normalizeStr(t))
      );

      const anyPassed = mustContainAny.length === 0 || mustContainAny.some((t) => answerNorm.includes(normalizeStr(t)));
      if (!anyPassed) {
        missingMustContain.push(`one of [${mustContainAny.join(', ')}]`);
      }

      const contentPassed = missingTrophies.length === 0 && missingMustContain.length === 0;
      const triadPassed = evaluation.faithfulness.score >= 0.8 && evaluation.answerRelevance.score >= 0.5;

      passed = contentPassed && triadPassed;
      if (missingTrophies.length > 0) {
        reasons.push(`Missing expected trophies: ${missingTrophies.join(', ')}`);
      }
      if (missingMustContain.length > 0) {
        reasons.push(`Missing required terms: ${missingMustContain.join(', ')}`);
      }
      if (!triadPassed) {
        reasons.push(
          `RAG Triad low score: Faithfulness=${evaluation.faithfulness.score} (expected >= 0.8), AnswerRelevance=${evaluation.answerRelevance.score}`
        );
      }
    }

    const output = {
      id: testCase.id,
      category: testCase.category,
      route: testCase.route,
      question: testCase.question,
      status: passed ? 'PASSED' : 'FAILED',
      answer: finalAnswer,
      isAbstained,
      toolCalls,
      reasons,
      evaluation,
    };

    console.log('__EVAL_RESULT_START__' + JSON.stringify(output) + '__EVAL_RESULT_END__');
    process.exit(0);
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    console.log(
      '__EVAL_RESULT_START__' +
      JSON.stringify({
        id: testCase.id,
        category: testCase.category,
        route: testCase.route,
        question: testCase.question,
        status: 'ERROR',
        error: errorMsg,
        evaluation: null,
      }) +
      '__EVAL_RESULT_END__'
    );
    process.exit(0);
  }
}

void main();
