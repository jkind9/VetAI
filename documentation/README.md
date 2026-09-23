# Design documents

- [Implementation plan](implementation-plan.md): ordered multi-chain flow, architecture, privacy boundaries, and deferred milestones.
- [Failure handling](failure-handling.md): complete error-to-action, retry, fallback, and desktop-state contract.
- [Approved sources](approved-sources.md): reviewed organisations, domains, enforcement, and evidence rules.
- [Test cases](test-cases.md): synthetic cases for standard questions, adaptive questions, retrieval, synthesis, safeguards, and failures.
- [Technical-test brief](../e071501d-5c3c-4368-9565-a0ba2b94ce0c_Tech_Test.pdf): original assignment.

The current milestone adds bounded live retrieval but not a vector database or stored RAG corpus.
Each chat turn is recorded in MLflow (see `src/mlflow_tracking`). It continues to defer customer
records, Postgres, an ERD, post-result chat, and production evaluation.
