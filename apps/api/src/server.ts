import { buildApp } from './app.js';
import { env } from './config/env.js';

// Insight: Graceful shutdown intercepts termination signals (SIGINT, SIGTERM) sent by Docker or Kubernetes.
// It stops accepting new requests, drains in-flight HTTP connections, and closes open resources
// before exiting with a clean status code 0, preventing dropped requests during zero-downtime rolling deploys.
const startServer = async () => {
  const app = await buildApp();

  const shutdown = async (signal: string) => {
    app.log.info({ signal }, 'Received termination signal, starting graceful shutdown...');
    try {
      await app.close();
      app.log.info('Server successfully closed. Exiting process.');
      process.exit(0);
    } catch (err) {
      app.log.error({ err }, 'Error during server shutdown.');
      process.exit(1);
    }
  };

  process.on('SIGINT', () => void shutdown('SIGINT'));
  process.on('SIGTERM', () => void shutdown('SIGTERM'));

  try {
    const address = await app.listen({
      port: env.PORT,
      host: env.HOST,
    });
    app.log.info(`🚀 Platina AI API running at: ${address}`);
  } catch (err) {
    app.log.fatal({ err }, 'Fatal error during server startup');
    process.exit(1);
  }
};

void startServer();
