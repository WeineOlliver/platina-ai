import Groq from 'groq-sdk';
import { env } from '../../config/env.js';
import { PLATINA_SYSTEM_PROMPT } from './prompts.js';

// Insight: The Strategy / Provider Adapter Pattern decouples business logic from external LLM vendors.
// Swapping between Groq (free Llama models), Anthropic (Claude), OpenAI, or local Ollama instances
// requires changing a configuration variable rather than refactoring route handlers.
export interface StreamChatOptions {
  systemPrompt?: string | undefined;
  signal?: AbortSignal | undefined;
}

export interface ILlmProvider {
  streamChat(prompt: string, options?: StreamChatOptions): AsyncGenerator<string>;
}

export class MockLlmProvider implements ILlmProvider {
  async *streamChat(prompt: string, options?: StreamChatOptions): AsyncGenerator<string> {
    const mockReply = `[Platina AI - Modo Demonstração]
Entendido! Sobre "${prompt}":
Antes de avançar, certifique-se de explorar todas as missões secundárias do capítulo para não perder nenhum troféu missable. 
(Configure GROQ_API_KEY no arquivo .env para respostas reais com Llama 3.3!)`;

    const words = mockReply.split(' ');
    for (const word of words) {
      if (options?.signal?.aborted) {
        break;
      }
      yield `${word} `;
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
  }
}

export class GroqLlmProvider implements ILlmProvider {
  private client: Groq;
  private model: string;

  constructor(apiKey: string, model: string = 'openai/gpt-oss-120b') {
    this.client = new Groq({ apiKey });
    this.model = model;
  }

  async *streamChat(prompt: string, options?: StreamChatOptions): AsyncGenerator<string> {
    const systemPrompt = options?.systemPrompt ?? PLATINA_SYSTEM_PROMPT;

    const stream = await this.client.chat.completions.create(
      {
        model: this.model,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: prompt },
        ],
        stream: true,
      },
      {
        signal: options?.signal,
      }
    );

    for await (const chunk of stream) {
      if (options?.signal?.aborted) {
        break;
      }
      const token = chunk.choices[0]?.delta?.content ?? '';
      if (token) {
        yield token;
      }
    }
  }
}

export const getLlmProvider = (): ILlmProvider => {
  if (process.env.AI_PROVIDER !== 'mock' && env.AI_PROVIDER === 'groq' && env.GROQ_API_KEY) {
    return new GroqLlmProvider(env.GROQ_API_KEY, env.GROQ_MODEL);
  }

  return new MockLlmProvider();
};
