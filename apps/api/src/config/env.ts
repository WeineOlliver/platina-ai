import { z } from 'zod';
import dotenv from 'dotenv';

// Load .env before parsing schema
dotenv.config();

// Insight: We use Zod for runtime schema validation instead of raw `process.env`.
// In high-scale production systems, failing fast during boot (fail-fast principle)
// prevents subtle bugs where a missing configuration causes runtime crashes halfway through a request.
const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: z.coerce.number().default(3000),
  HOST: z.string().default('0.0.0.0'),
  LOG_LEVEL: z.enum(['fatal', 'error', 'warn', 'info', 'debug', 'trace']).default('info'),
  CORS_ORIGIN: z.string().default('*'),
  AI_PROVIDER: z.enum(['mock', 'groq', 'anthropic', 'openai']).default('groq'),
  GROQ_API_KEY: z.string().optional(),
  GROQ_MODEL: z.string().default('llama-3.3-70b-versatile'),
  ANTHROPIC_API_KEY: z.string().optional(),
  OPENAI_API_KEY: z.string().optional(),
  INGESTION_SERVICE_URL: z.string().url().default('http://localhost:8000'),
});

const parseEnv = () => {
  const result = envSchema.safeParse(process.env);

  if (!result.success) {
    console.error('❌ Invalid environment variables:', JSON.stringify(result.error.format(), null, 2));
    throw new Error('Invalid environment configuration');
  }

  return result.data;
};

export type Env = z.infer<typeof envSchema>;
export const env = parseEnv();
