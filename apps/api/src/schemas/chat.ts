import { z } from 'zod';

// Insight: We define strict input contracts using Zod.
// Validating user input before opening a long-lived streaming connection prevents
// unauthenticated or malformed requests from tying up server resources.
export const chatRequestSchema = z.object({
  message: z.string().min(1, 'Message cannot be empty').max(4000, 'Message is too long (max 4000 chars)'),
  conversationId: z.string().uuid().optional(),
  game: z.string().optional(),
});

export type ChatRequest = z.infer<typeof chatRequestSchema>;

export type ChatStreamChunk = {
  type: 'chunk' | 'done' | 'error';
  content?: string;
  conversationId?: string;
  error?: string;
};
