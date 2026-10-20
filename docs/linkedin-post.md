# Platina AI: High-Impact LinkedIn Post

---

## 📱 Post Content (Copy-Paste Ready)

Most RAG pipelines break when real-time data hides behind Cloudflare anti-bot walls or requires live account telemetry. Out-of-the-box LLMs hallucinate guide steps and invent non-existent items.

The pain point? Missable trophies. In The Witcher 3, missing 1 of 199 Gwent cards permanently burns 80+ hours of gameplay on a ruined Platinum run.

I built Platina AI—an autonomous assistant syncing live PSN telemetry with verified walkthroughs to guarantee zero-spoiler, zero-miss trophy routes:

• Sub-1.5s TTFT via Context Pre-fetching: Injects synthesized PSN tool turns upfront, bypassing multi-roundtrip ReAct loops.
• Resilient Scraping vs. Cloudflare WAF: Fast HTTP extraction with automated Playwright Chromium fallback on 403 challenges.
• Pre-Flight Grounding Validator: Pre-checks guide prerequisites before opening the SSE stream—zero hallucinated steps.
• $0 Dev Cost Multi-Model Cascade: Dynamic fallback tier (gpt-oss-120b → gpt-oss-20b → qwen-27b) handling 429 TPD quota exhaustion.
• Hybrid RAG: Reciprocal Rank Fusion (RRF) combining dense pgvector embeddings with sparse BM25 tsvector search.

Stack: TypeScript/Fastify • Python/FastAPI • PostgreSQL 16 (pgvector) • Docker • k3s on AWS Graviton

Repo, 5 ADRs, and 61 technical interview prep deep-dives in the first comment 👇 How do you handle Cloudflare WAF fallbacks in your ingestion pipelines?

#SoftwareEngineering #SystemDesign #RAG #AI #FullStack #TypeScript #Python #DevOps

---

## 💬 First Comment (Copy-Paste Ready)

🔗 Full repository & documentation:
https://github.com/WeineOlliver/platina-ai

📚 61 Technical Interview Prep Deep-Dives & ADRs:
https://github.com/WeineOlliver/platina-ai/blob/main/docs/interview-prep.md
https://github.com/WeineOlliver/platina-ai/blob/main/docs/architecture.md

🎥 Demo video & architecture assets:
https://github.com/WeineOlliver/platina-ai/tree/main/docs/media

---

## 📋 Publication Checklist & Best Practices

- [ ] **Optimal Timing:** Schedule for **Tuesday at 10:00 BRT / 9:00 EDT** (peak window for US/EU engineering leaders & technical recruiters).
- [ ] **Native Video Attachment:** Attach `docs/media/platina-ai-demo.mp4` directly to the post (MP4 H.264, web-optimized with faststart, ~35s).
- [ ] **Zero Links in Body:** Ensure no external URLs are in the post body (prevents LinkedIn algorithm downranking).
- [ ] **Immediate First Comment:** Post the prepared first comment within 30 seconds of publication.
- [ ] **Golden Hour Engagement:** Respond to all comments within the first 60 minutes to maximize reach velocity.
