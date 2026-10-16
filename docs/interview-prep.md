# Technical Interview Prep & Soundbites — Platina AI

This document contains real-world technical interview questions, key engineering concepts, and concise 60-second answers (*soundbites*) in English for each architectural component of Platina AI.

---

## Milestone 1: Core API & Server Architecture (Fastify + TypeScript)

### Q1: System Design & Factory Pattern
> **"Why did you decouple the HTTP application definition from the network listener using an application factory pattern, and what specific advantages does this offer during CI/CD test automation?"**

- **Core Concept:** Separating `buildApp()` (route registration and plugins) from `app.listen()` (TCP socket binding) allows testing the HTTP application in-memory via `app.inject()`.
- **Key Engineering Benefits:**
  - Avoids port collision errors (`EADDRINUSE`) when multiple test suites run in parallel in CI/CD pipelines.
  - Zero network overhead: tests execute 5-10x faster directly against the event loop.
- **60-Second Interview Soundbite:**
  > *"I decoupled the app creation using a factory pattern—`buildApp()`—so that server instantiation is separated from socket binding. In CI/CD pipelines, this allows us to run integration tests concurrently in memory using Fastify's native `inject()` API. It completely eliminates port collisions (`EADDRINUSE`), avoids network overhead, and makes our test suite significantly faster."*

---

### Q2: Reliability & Graceful Shutdown
> **"How does the graceful shutdown mechanism work when running inside a containerized environment (like Kubernetes or ECS), and what would happen to in-flight client requests if `SIGTERM` wasn't handled explicitly?"**

- **Core Concept:** When Kubernetes performs a rolling update or scales down a pod, it sends a POSIX `SIGTERM` signal before issuing a forceful `SIGKILL`.
- **The Problem Without It:** Without explicit signal handling, the process immediately dies, severing active client TCP sockets, breaking long-lived SSE streaming responses, and producing HTTP 502 Bad Gateway errors at the load balancer.
- **How We Solve It:** We register listeners on `process.on('SIGTERM')` and `process.on('SIGINT')` that trigger `app.close()`. Fastify stops accepting new incoming traffic while allowing active in-flight requests to drain and finish cleanly before terminating with exit code 0.
- **60-Second Interview Soundbite:**
  > *"When Kubernetes scales down a pod or performs a rolling update, it sends a `SIGTERM` signal. Without handling it, the container runtime forcefully terminates the process, immediately dropping any active connections—which creates 502 errors and a broken experience for users in the middle of an AI streaming response. By listening to `SIGTERM` and calling `app.close()`, we stop accepting new traffic, allow in-flight requests to complete cleanly, and close open resources before exiting with code 0."*

---

### Q3: Framework Trade-offs (Fastify vs. Express vs. NestJS)
> **"Why did you opt for Fastify over Express.js or NestJS for the core API layer of an AI streaming product?"**

- **Core Concept:** Different Node.js web frameworks have distinct overhead, throughput, and ergonomics profiles.
- **Comparison:**
  - **Vs. Express:** Express has higher per-request overhead, lacks native modern TypeScript typing, and relies on older callback/middleware patterns not optimized for high-throughput streaming. Fastify offers up to 2-3x higher throughput, native schema-based JSON serialization, and first-class async plugin lifecycle.
  - **Vs. NestJS:** While NestJS provides enterprise structure, its heavy decorator-based dependency injection adds runtime bloat and increases cold-start times in serverless or auto-scaled containers. Fastify provides a clean, modular plugin architecture without unnecessary abstractions.
- **60-Second Interview Soundbite:**
  > *"For an AI product heavily focused on streaming (SSE) and low latency, Fastify was the best fit over Express and NestJS. Compared to Express, Fastify provides significantly lower overhead, first-class TypeScript support, and optimized JSON serialization. Compared to NestJS, it avoids unnecessary architectural bloat and heavy dependency injection wrappers, keeping the container lightweight with very fast cold-start times."*
