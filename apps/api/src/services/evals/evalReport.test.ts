import { describe, it, expect } from 'vitest';
import { runConsolidatedEvals, formatEvalReportAsMarkdown } from './evalReport.js';

describe('Consolidated Evals Report Suite', () => {
  it('runs all eval batteries and aggregates RAG Triad and Agent Trajectory metrics into a structured report', async () => {
    const report = await runConsolidatedEvals();

    expect(report.timestamp).toBeTruthy();
    expect(report.totalScenarios).toBeGreaterThanOrEqual(4);
    expect(report.summary.ragTriadAverage).toBeGreaterThanOrEqual(0.7);
    expect(report.summary.trajectoryAverage).toBeGreaterThanOrEqual(0.7);
    expect(report.summary.passRate).toBeGreaterThanOrEqual(0.75);
    expect(report.results.length).toBe(report.totalScenarios);
  }, 30000);

  it('formats evaluation results into a clean, human-readable markdown table', async () => {
    const report = await runConsolidatedEvals();
    const markdown = formatEvalReportAsMarkdown(report);

    expect(markdown).toContain('# Platina AI — Relatório Consolidado de Evals');
    expect(markdown).toContain('| Cenário | Context Relevance | Faithfulness | Answer Relevance | Trajectory | Status |');
    expect(markdown).toContain('Taxa de Aprovação:');
  }, 30000);
});
