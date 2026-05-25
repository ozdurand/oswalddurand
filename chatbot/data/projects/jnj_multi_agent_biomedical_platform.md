# J&J Multi-Agent Biomedical Research Platform

> A production multi-agent LLM platform that lets biomedical scientists and drug safety teams query 10,000+ internal scientific documents in natural language, with regulatory-grade audit trails.

## Overview
J&J's biomedical scientists and drug safety teams were spending hours per week manually searching across siloed scientific document repositories — protocols, study reports, safety narratives, ontology references — to answer questions that often required synthesis across multiple sources. We built a multi-agent LLM platform on AKS that lets them ask those questions in natural language and get cited, audit-logged answers in seconds. The system serves 120 concurrent sessions at p95 latency under 900ms and is in production across multiple therapeutic areas.

## Why
A senior scientist asking "what adverse events have we seen across our oncology portfolio for patients with hepatic impairment?" used to mean hours of manual cross-referencing: pulling protocols from one system, narratives from another, ontology mappings from a third, then synthesizing by hand. Drug safety teams faced regulator-imposed turnaround pressure (FDA, EMA) and could not afford analyst time spent on retrieval rather than judgment.

The alternative was hiring more analysts or buying a vertical SaaS product — neither acceptable. The SaaS options could not be trusted with internal pre-publication data, and headcount does not scale with corpus growth. A general-purpose LLM with naive RAG was inadequate because biomedical questions almost always require structured tool use (ontology lookup, drug safety database queries, study filtering) alongside semantic retrieval, and because every response had to be traceable for regulatory review.

## What
Built: a 5-agent specialist system (Knowledge, Ontology, Drug Safety, QA, Summarization) coordinated by an LLM Orchestrator meta-agent, totaling 15 tools across 6 agents. Ingestion and indexing pipeline for 10,000+ scientific documents. Streaming chat UI with agent trace panel for transparency. Full observability stack: OpenTelemetry spans, custom App Insights events, correlation ID propagation, structured Cosmos DB audit logs sufficient for regulatory review. Role-based access scoped by therapeutic area.

Explicit non-goals: not a clinical decision support tool (no patient-level recommendations); not a regulatory submission generator (output is research-assist, not filing-ready); not a general enterprise chatbot (scoped to scientific corpus, not HR or IT questions).

## How — Architecture
The system is organized around an LLM Orchestrator (GPT-4o) that handles intent classification, planning, fan-out to specialist agents, and final response assembly natively in-model. Five specialist agents each own a narrow domain: Knowledge Agent (semantic retrieval over the document corpus), Ontology Agent (MeSH / MedDRA / internal taxonomy resolution), Drug Safety Agent (structured queries against pharmacovigilance datasets), QA Agent (fact verification and citation checking), and Summarization Agent (long-form synthesis with citation preservation). Each specialist exposes exactly 2 tools; the Orchestrator owns 5 hard tool calls for external I/O (auth, audit log write, citation resolver, user preferences, escalation handoff).

Data flow: user query → Orchestrator → specialist agent fan-out (parallel where independent, sequential where dependent) → QA verification pass → Orchestrator assembles final answer with citations → audit record written to Cosmos DB → streamed to user with agent-trace metadata.

Key dependencies: Azure OpenAI (GPT-4o), Azure AI Search for vector + hybrid retrieval, Cosmos DB for audit and session state, Azure Blob for source documents, AKS for compute, App Insights for telemetry.

## How — Tech Stack
Python (FastAPI backend), TypeScript / React for the chat UI. Azure OpenAI for GPT-4o orchestration and embeddings. Azure AI Search for hybrid retrieval. AKS for deployment with HPA on session-bound replicas. Cosmos DB for audit logs and session state. OpenTelemetry instrumentation, Azure App Insights for traces / metrics / custom events, Grafana for dashboards. CI/CD via Azure DevOps with environment promotion gates. OpenAI Agents SDK primitives (Agent, Runner, trace) underpin the agent abstraction layer.

## Journey: POC
Initial hypothesis: a single-agent RAG system over the document corpus would cover most questions, with structured lookups added later if needed. Built `ingest.py` and `rag.py` as a foundational layer — FAISS local vector store, OpenAI embeddings, GPT-4o for synthesis, Streamlit retrieval debugger as the first UI.

What was learned: single-agent RAG was the wrong shape. Biomedical questions almost always require structured side-information (drug code resolution, study filtering, ontology disambiguation) before semantic retrieval is even useful. A question like "AEs for compound X in Phase II hepatic-impaired cohorts" needs the compound resolved, the studies filtered, and the AE taxonomy normalized before retrieval has anything sensible to search. We pivoted from one-agent-with-tools to a specialist-agent decomposition.

## Journey: MVP
What got hardened: the specialist agent boundaries (one domain per agent, two tools per agent — strict), the streaming chat UI with agent trace panel, and a first cut at audit logging.

New requirements that emerged: regulatory affairs flagged that every response needed end-to-end traceability — not just "what did the model say" but "which documents were retrieved, which tools were called with which arguments, which agent produced which sentence." That forced a redesign of the audit log schema and introduction of correlation IDs propagated through every agent and tool call. Identity and role-based scoping (therapeutic area, data-access tier) were added so that a scientist on one program could not retrieve documents from another.

Decisions under pressure: chose the LLM-as-Orchestrator pattern (GPT-4o handling routing, planning, fan-out, and assembly natively) over a hand-coded router. Faster to iterate, better at ambiguous queries, and the trace overhead was acceptable. Retained 5 hard tool calls for external I/O where determinism matters.

## Journey: Production
Reliability: deployed on AKS with HPA, multi-replica with session affinity, circuit breakers around Azure OpenAI to degrade gracefully on throttling. Observability: OpenTelemetry spans across every agent and tool call, custom App Insights events for business-level signals (query type, agent invocation count, citation count, fallback paths), Grafana dashboards for SREs and a separate scientist-facing trace panel.

Scale targets: 120 concurrent sessions, p95 end-to-end latency under 900ms, sustained. Security and regulatory: corporate SSO, role-based access by therapeutic area, full audit log retention sufficient for FDA / EMA inspection, no PII or patient-level data in scope.

On-call: lightweight rotation among the engineering team, runbook-driven. The most common failure mode is Azure OpenAI throttling — handled via the circuit breaker and a queued retry path rather than waking anyone up.

## Key Decisions & Tradeoffs
LLM Orchestrator over hand-coded router — chose flexibility and faster iteration over deterministic control flow; would revisit only if response variance ever becomes a regulatory blocker (it hasn't).

Two-tools-per-agent rule — chose simplicity and easy reasoning about agent behavior over a single all-purpose agent with 15 tools. The tradeoff is more inter-agent calls, but the trace clarity has been worth it during audits.

Azure AI Search for hybrid retrieval rather than a pure vector DB — chose ecosystem fit (already on Azure, regulatory posture pre-cleared) over best-in-class vector performance.

OpenTelemetry plus App Insights custom events rather than a single observability product — chose vendor portability for the OTEL layer while still getting Azure-native query power. Would revisit if cardinality costs ever bite.

## Outcomes
22% improvement in research turnaround time, measured against pre-platform baseline workflows. 18% reduction in hallucinated or unsupported claims, measured by QA-agent flagging against the prior single-agent baseline. 120 concurrent sessions sustained with p95 end-to-end latency under 900ms. Audit trail accepted in regulatory readiness review.

Lessons: the specialist-agent decomposition was the single highest-leverage architectural choice — it made every subsequent observability, auditability, and reliability decision easier. The LLM-as-Orchestrator pattern is underrated for systems where ambiguity tolerance matters more than deterministic dispatch. And the discipline of "two tools per agent" paid for itself many times over in debuggability.
