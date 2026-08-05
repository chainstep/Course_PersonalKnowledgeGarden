# Framework decision

PydanticAI gives the agent layer typed, lightweight agents with configurable models and deterministic testing support. Storage, retrieval, security, and MCP remain framework-independent, preserving a typed boundary between untrusted content and agent behavior.

If workflows grow to need durable state, branching, retries, or long-running orchestration, migrate the isolated agent runner to LangGraph. The service layer already keeps agents separate, so that migration remains local rather than a rewrite.
