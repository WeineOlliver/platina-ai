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

---

## Milestone 1: Server-Sent Events (SSE) Streaming Endpoint (`POST /api/v1/chat`)

### Q4: Streaming Protocol Trade-offs (SSE vs. WebSockets vs. gRPC Web)
> **"Why did you choose Server-Sent Events (SSE) instead of WebSockets or gRPC-Web for streaming LLM responses in Platina AI?"**

- **Core Concept:** LLM text generation is fundamentally unidirectional: the client sends one prompt message, and the server replies with a sequence of tokens over time.
- **Why SSE Wins for LLM Chat:**
  - **Unidirectional Fit:** WebSockets are designed for full-duplex, bidirectional communication (e.g., multiplayer games, collaborative whiteboards). LLM chat doesn't need client-to-server messaging mid-stream.
  - **HTTP/1.1 & HTTP/2 Compatibility:** SSE operates over standard HTTP requests. It works effortlessly through firewalls, standard API gateways, and corporate proxies without WebSocket upgrade negotiation.
  - **Native Client Support:** Modern browsers and clients consume SSE natively via `EventSource` or `ReadableStream` (`fetch`).
  - **Automatic Reconnection & Standard Headers:** Carries standard HTTP authentication (Bearer tokens, cookies), whereas WebSockets do not support custom authorization headers in standard browser APIs.
- **60-Second Interview Soundbite:**
  > *"For streaming LLM responses, Server-Sent Events (SSE) is technically superior to WebSockets. LLM generation is inherently unidirectional: one prompt produces a stream of tokens. SSE operates over standard HTTP, avoiding WebSocket connection upgrade handshakes, and natively supports standard HTTP headers for authentication and tracing. It eliminates stateful WebSocket gateway complexity while giving clients immediate real-time token rendering."*

---

### Q5: Reverse Proxy Buffering & Zero-Latency Streaming (`X-Accel-Buffering`)
> **"What is the significance of the `X-Accel-Buffering: no` header in an SSE streaming response when deploying behind reverse proxies like Nginx, Cloudflare, or AWS Application Load Balancers?"**

- **Core Concept:** By default, reverse proxies (like Nginx) buffer upstream responses in chunks (e.g., 4KB or 8KB buffers) to optimize network packet efficiency before sending them to the client.
- **The Failure Mode:** If buffering is active on an SSE route, the client sees nothing for several seconds while tokens accumulate in the proxy's buffer, then receives a sudden burst of text. This completely destroys the perceived low-latency user experience of LLM streaming.
- **How We Solve It:** Sending `X-Accel-Buffering: no` instructs reverse proxies to disable response buffering and immediately flush each SSE frame (`data: ...\n\n`) over the wire the microsecond it is written.
- **60-Second Interview Soundbite:**
  > *"Reverse proxies like Nginx and API Gateways buffer responses by default to maximize TCP packet efficiency. In an SSE streaming context, this creates latency lag because the proxy holds tokens until its buffer fills up before sending them to the user. By sending `X-Accel-Buffering: no` alongside `Cache-Control: no-cache, no-transform`, we explicitly instruct proxies and CDNs to disable buffering and immediately flush each generated token to the client."*

---

### Q6: Client Disconnection & Resource Leak Prevention
> **"How do you handle client disconnections during an active LLM streaming response, and why is this critical for cost and compute optimization?"**

- **Core Concept:** If a user closes their browser tab or navigates away while an LLM is generating a 500-token response, continuing generation wastes API credits (Anthropic/OpenAI token costs) and consumes server memory/CPU.
- **How We Solve It:** We intercept socket closure events (`reply.raw.on('close')`) and check `!reply.raw.writableFinished`. If the socket closed before the stream naturally completed, we signal an `AbortController`. The async generator intercepts `signal.aborted`, halts further processing, breaks the loop, and releases server resources immediately.
- **60-Second Interview Soundbite:**
  > *"When a user closes their tab mid-generation, continuing inference wastes expensive API tokens and keeps Node.js event loop handles open. In Platina AI, we listen for socket termination on the raw HTTP response. If the client disconnects before `writableFinished`, we trigger an `AbortController`. The streaming async generator detects the abort signal, immediately stops pulling tokens, and tears down resources, preventing phantom compute and wasted token costs."*

