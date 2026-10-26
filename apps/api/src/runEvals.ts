import { runConsolidatedEvals, formatEvalReportAsMarkdown } from './services/evals/evalReport.js';

async function main() {
  console.log('🧪 Iniciando Bateria de Evals do Platina AI (RAG Triad + Agent Trajectory)...');
  const startTime = Date.now();

  try {
    const report = await runConsolidatedEvals();
    const durationSec = ((Date.now() - startTime) / 1000).toFixed(1);

    console.log('\n' + formatEvalReportAsMarkdown(report));
    console.log(`\n⏱️  Tempo total de execução: ${durationSec}s`);

    if (report.summary.passRate < 0.75) {
      console.error('\n❌ Evals falharam no gate de qualidade (taxa de aprovação < 75%).');
      process.exit(1);
    } else {
      console.log('\n✅ Todos os gates de qualidade passaram com sucesso!');
      process.exit(0);
    }
  } catch (err) {
    console.error('❌ Erro fatal na execução dos evals:', err);
    process.exit(1);
  }
}

void main();
