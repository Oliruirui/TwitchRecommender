# Project notebook

Designs, learning notes and recorded experiment results for building TwitchRecommender step by step. These notes describe a local CPU project with no additional paid services.

## Where to start

- [High-level design](notes/TwitchRecommender-HLD-v0.1.md)
- [Working low-level design](notes/TwitchRecommender-LLD-v0.1.md): agreed details and future proposals; not all planned components exist yet.
- [Current Python installation, training, export and API instructions](../recommendation/README.md)
- [Spring Boot migration](notes/Spring-Boot-Migration-Design.md): design, [implementation plan](notes/Spring-Boot-Migration-Implementation-Plan.md) and [verification results](notes/Spring-Boot-Migration-Results.md).

## Implemented milestones

| Milestone | Notes and evidence | Code |
|---|---|---|
| Data preparation and popularity baseline | [Results](notes/Offline-Milestone-Results.md), [original plan](notes/TwitchRecommender-Data-Baseline-Task-Plan.md) | [Merged PR #1](https://github.com/Oliruirui/TwitchRecommender/pull/1) |
| Two-tower training | [Initial results](notes/Two-Tower-Milestone-Results.md), [original plan](notes/TwitchRecommender-Two-Tower-Training-Plan.md) | [Merged PR #2](https://github.com/Oliruirui/TwitchRecommender/pull/2) |
| Ten vs. thirty epochs | [Experiment and learning curves](notes/Retrieval-Diagnosis-2026-10-13.md) | Controlled local experiment; repository defaults remain ten epochs |
| FAISS export | [Results and verification](notes/FAISS-Export-Milestone.md) | [Merged PR #3](https://github.com/Oliruirui/TwitchRecommender/pull/3) |
| Python retrieval API | [Results](notes/Python-Retrieval-Service-Results.md), [original plan](notes/Python-Retrieval-Service-Implementation-Plan.md), [HTTP responses](notes/Python-Retrieval-Service-HTTP-Results.json) | [Merged PR #4](https://github.com/Oliruirui/TwitchRecommender/pull/4) |

The original [project implementation outline](notes/TwitchRecommender-Implementation-Plan-v0.1.md) records early assumptions. Newer approved milestone designs take precedence. The Spring Boot decision supersedes the earlier plan to retain plain Servlets; the Java-to-Python integration remains a separate later PR.

## Java migration

The [Spring Boot backend](notes/Spring-Boot-Migration-Results.md) replaces the legacy Servlet/WAR setup. Its [migration PR #6](https://github.com/Oliruirui/TwitchRecommender/pull/6) is open for review; Java-to-Python recommendation integration is the next milestone. Run Java under JDK 21 and use the checked-in Maven Wrapper.

## Learning notes

- Training uses historical interactions to learn user/channel representations. Serving uses the already-trained model and FAISS index; it does not train per request.
- Current predictions use dataset user identities and the history represented in training. New application activity is not connected yet. Unknown users receive popular channels.
- FastAPI's `/docs` is generated API documentation/testing UI. The recommendation frontend has not been built.
- Retraining remains manual for now. Revisit scheduling after Java integration and event collection; daily training is a possible starting proposal, not an implemented default.
- Higher validation Recall/NDCG in the thirty-epoch experiment is offline evidence, not proof of online engagement lift. The frozen test split remains reserved.
- Docker/Linux execution and throughput targets remain unverified. Existing test counts in milestone reports are snapshots from their respective dates.

At the end of the project, revisit why two towers were chosen, what the examples/loss teach, negative sampling, evaluation/leakage, and cold-start users/channels.

## What is stored here

Markdown notes, small aggregate metric reports, example API responses, an experiment configuration and a learning-curve chart. Workstation-specific Python commands were normalized to `.venv/bin/python`; raw evidence values were retained, with absolute workstation paths removed where present. Plans retain their original checklist states for historical context.

Raw datasets, user-event tables, trained weights, FAISS indexes, credentials, patches and internal execution logs are not included. Source changes are available through their PRs. Files named as training/export outputs in examples are generated locally; this notebook does not supply those artifacts. Runtime manifests here are examples from a recorded run, not deployable bundles.
