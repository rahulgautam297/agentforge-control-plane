# agentforge-control-plane

**Status:** Not yet implemented — see `../agentforge-docs/docs/architecture/12-implementation-plan.md`, Phase 1.

## Purpose

This repo will host the AgentForge control plane: a Python + FastAPI +
Pydantic service that owns the Agent Registry, the YAML Validator's semantic
layer, the Model/Tool/Knowledge Registries, the Policy Engine (authoring
side), the Deployment Manager, and the Evaluation Manager. It is the sole
schema-migration owner (via Alembic) of the shared `agentforge` TimescaleDB
database. See
`../agentforge-docs/docs/architecture/02-component-responsibilities.md` and
`../agentforge-docs/docs/architecture/06-repository-structure.md` for how
this repo fits into the wider polyrepo, and
`../agentforge-docs/docs/architecture/03-control-plane.md` and
`../agentforge-docs/docs/architecture/08-database-schema.md` for its
internals.

## Depends on

- `agentforge-agent-schema` — pinned git dependency, used as the structural
  layer of YAML validation before this service's own semantic checks run.

## Related documentation

- [Architecture overview](../agentforge-docs/docs/architecture/01-overview.md)
- [Control plane](../agentforge-docs/docs/architecture/03-control-plane.md)
- [Database schema](../agentforge-docs/docs/architecture/08-database-schema.md)
- [Component responsibilities](../agentforge-docs/docs/architecture/02-component-responsibilities.md)
- [Repository structure](../agentforge-docs/docs/architecture/06-repository-structure.md)
