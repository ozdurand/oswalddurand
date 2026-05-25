# Citibank Model Operations Platform on AWS

> An MLOps platform for Citibank's quantitative modeling teams that brought training, validation, and deployment under SR 11-7-aligned governance on AWS.

## Overview
Citibank's quantitative modeling teams were producing risk, pricing, and analytics models on individually owned laptops and bespoke servers, with model validation and promotion handled through email, spreadsheets, and ad-hoc handoffs. We built an MLOps platform on AWS that gave those teams a paved road from notebook to production with reproducible training, versioned model artifacts, automated validation packets, and a deployment path that satisfied SR 11-7 model-risk governance.

## Why
In a regulated banking environment, every model that touches a business decision is subject to SR 11-7: independent validation, ongoing monitoring, documented assumptions, traceable lineage from training data to production prediction. Doing this by hand is expensive and slow — model validators were spending most of their time reconstructing what the developer had done, instead of validating it.

The alternative was the status quo: months between a model being ready and a model being live, validators chasing developers for environment details, and a steady accumulation of unreviewed model variants on individual machines. That was a regulatory risk, an audit risk, and a business risk — risk-management decisions were waiting on operational overhead.

The opportunity was to encode the governance flow into the platform itself: if the path of least resistance produced a validation-ready, reproducible, auditable model, validators got their lives back and developers got their models live faster.

## What
Built: a model training and registration platform on AWS with SageMaker as the training compute, S3 as the immutable artifact and dataset store, and a model registry that captured lineage from input data through training code through hyperparameters through evaluation metrics. Automated assembly of validation packets — the documentation artifacts SR 11-7 validators expect — from the registered model and its training run. Deployment pipelines that gated promotion on validator sign-off and produced a tamper-evident audit trail. Standard model templates and project scaffolds so quants started on the paved road rather than off of it.

Explicit non-goals: not building the models themselves (that remained with the quant teams); not replacing the independent validation function (the platform served validators, it did not substitute for them); not a real-time inference platform for low-latency trading systems (those had their own purpose-built infrastructure with different governance).

## How — Architecture
The platform sits between the modeling teams and the production environments. A developer working in a managed JupyterLab environment uses platform-provided scaffolds to wire training code to a reproducible runtime image, pulls training data from governed S3 datasets, and submits training jobs to SageMaker. Every training run produces an immutable artifact bundle in S3: code commit hash, environment image digest, dataset version, hyperparameters, metrics, and the model binary.

That bundle is registered to the model registry, which becomes the single source of truth. Validators access the registry through their own UI, pull validation packets generated from the registered run, and record their sign-off in the same system. Promotion to a deployment environment is gated on registry state — no sign-off, no deploy. Deployments go through CI/CD pipelines that pull artifacts from the registry, deploy to ECS or SageMaker endpoints depending on use case, and emit deployment events back to the registry and to the audit log.

Monitoring is wired in at deployment time: every promoted model gets a baseline CloudWatch dashboard and a drift / performance monitoring job that writes back to the registry.

## How — Tech Stack
AWS as the compute and storage substrate: SageMaker for training, S3 for artifacts and datasets, ECS and EKS for serving, Lambda for glue, Step Functions for pipeline orchestration, CloudWatch for monitoring and alerting, IAM for access scoping. MLflow as the model registry backbone, integrated with the firm's existing identity and entitlement systems. Python and PySpark on the modeling side; the production model surface was a mix of Python services and JVM-based scoring containers. Jenkins for CI/CD with custom shared libraries enforcing governance gates. Docker for environment reproducibility. Terraform for platform infrastructure. Splunk for centralized logging into the firm's standard observability environment.

## Journey: POC
Initial hypothesis: a single quant team could be moved from laptop-based training to a platform-based workflow in a quarter, and the resulting reproducibility would be obvious enough to validators that they would actively pull rather than passively wait.

Scope: one pilot team, one model family, end-to-end flow from JupyterLab through SageMaker training through MLflow registration through a stub validation handoff. No production deployment in the POC — the goal was to prove the lineage story.

What was learned: the reproducibility win was real and obvious. The friction was almost entirely in the on-ramp — getting a developer's notebook to run unchanged inside the platform's runtime image, with the platform's dataset access pattern, took more handholding than expected. The lesson was that the platform needed strong scaffolds and templates, not just primitives. We also learned that validators were a more demanding user than developers — they wanted the validation packet in a specific format with specific metadata, and that format was not optional.

## Journey: MVP
What got hardened: the runtime image story (base images per language and framework, owned by the platform team, scanned and patched on a regular cadence), the dataset access pattern (governed S3 prefixes with IAM-scoped access, dataset versioning), and the validation packet generator (deterministic output, regenerable from registry state).

New requirements that emerged: model risk management formally asked for full lineage from production prediction back to training data row — meaning the platform had to capture and persist dataset versions, not just dataset names. Information security required all training environments to be locked down: no arbitrary outbound network, only approved package mirrors. Internal audit asked for a tamper-evident audit log of every promotion event, separate from the registry's own state.

Decisions under pressure: chose MLflow as the registry rather than building one — the data model was close enough to what we needed and the cost of build-from-scratch was unjustifiable. Chose to invest heavily in scaffolds and templates rather than expecting teams to compose primitives themselves. The platform's job was to make the right thing easy.

## Journey: Production
Reliability: multi-region within AWS with active-passive failover for the registry and CI/CD planes. Training jobs were tolerant to SageMaker capacity issues with automatic retry and queueing. Promotion pipelines were idempotent with explicit reconciliation against registry state on every run.

Observability: CloudWatch dashboards for platform health, Splunk dashboards for governance signals (model count by lifecycle state, time-to-validation, time-to-deploy, failed promotion attempts and reasons). A weekly governance report rolled up to model risk leadership.

Scale: a few hundred active models across the participating businesses, several thousand training runs per month at peak. Security and regulatory: SR 11-7-aligned model lifecycle, full audit trail, IAM-scoped data access, runtime images scanned against the firm's security baseline, change-management integration for production promotions.

On-call: rotation across the platform team, runbook-driven, with most pages relating to capacity in shared AWS services rather than platform code.

## Key Decisions & Tradeoffs
MLflow registry over custom build — chose ecosystem and time-to-value over perfect fit. We extended MLflow with governance metadata rather than reinventing the data model. Would revisit only if MLflow's roadmap diverged from regulated-environment needs.

Paved road over freedom — chose strong scaffolds, opinionated templates, and locked-down runtime images over giving quants maximum flexibility. The tradeoff was real onboarding friction for unusual workflows, but the validation and audit story would not have held together otherwise.

SageMaker as primary training compute rather than self-managed EKS — chose managed-service operational simplicity over the lower per-job cost of self-managed compute. The platform team headcount we did not spend on operating training infrastructure went into governance tooling instead.

Generated validation packets rather than free-form documentation — chose deterministic, regenerable output over developer-authored narrative. Validators got what they needed in a predictable format and developers stopped writing the same Word document three times per model.

## Outcomes
Brought several hundred models under platform governance over the tenure, materially compressing the path from model-ready to model-deployed. Validation packets generated automatically from registry state replaced the prior cycle of email, attachments, and re-runs. Audit and model risk management reviews proceeded against platform-generated artifacts directly.

Lessons: in a regulated environment, the right unit of MLOps work is the *governance flow*, not the *training pipeline* — the training pipeline is the easy part. The platform's most valuable artifact was the validation packet, not the trained model. And making the paved road the path of least resistance — strong scaffolds, locked-down runtimes, opinionated templates — was what made the governance story hold up under audit pressure.
