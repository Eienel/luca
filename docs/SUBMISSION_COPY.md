# Devpost submission copy

## Project name

ChangeSafe by Luca

## One-line description

ChangeSafe turns DataHub's organizational dependency graph into tested migration
code, a Git-ready review package, and a durable change decision before a schema
change breaks downstream teams.

## Primary category

Metadata-Aware Development

This is the clearest fit because the core user is a developer proposing a schema
change, and the differentiating mechanism is using DataHub metadata during that
development workflow. Luca's broader agent suite remains the roadmap,
not a competing submission claim.

## Inspiration

A producer's tests can be green while a column rename breaks Finance dashboards,
Growth models, Support workflows, and ML features. The missing information is not
inside the producer repository: it is distributed across lineage, query history,
ownership, domains, and column-level dependencies. DataHub already contains that
organizational graph. ChangeSafe makes it executable at change-review time.

## What it does

ChangeSafe reads a shared dataset, its schema, downstream lineage, column-level
paths, and query examples through DataHub MCP. It builds an evidence-backed
Luca, scores cross-team convergence, and pressure-tests a proposed rename,
removal, or type change. It then identifies known affected consumers, reports
unknown coverage, generates compatibility SQL and regression SQL, creates a
four-file review package, applies that package as a real Git branch and commit,
and records the reviewed decision back in DataHub.

## How we built it

- FastAPI serves a compact browser workflow and deterministic analysis engine.
- DataHub MCP provides entity, schema, lineage, query, and document operations.
- A local dbt-shaped SQLite fixture proves the break and generated repair without
  a paid warehouse or API.
- A public GitHub Actions workflow boots DataHub OSS and the official MCP server,
  ingests DataHub's sample metadata, exercises column lineage, saves the decision,
  and reads the saved document back.
- Generated changes are reviewable SQL and Markdown; an LLM is not trusted to
  decide whether a change is safe.

## Challenges

The largest challenge was preserving evidence boundaries. Lineage and query
history can show known consumers but cannot prove complete coverage, so the UI
always carries an unknown-coverage warning. We also found multiple valid response
wrappers in the official MCP server and added contract tests plus a live durability
check instead of masking those differences.

## Accomplishments

- A real rename breaks four downstream SQL consumers; the generated compatibility
  layer repairs all four with zero mismatches.
- The live workflow loads actual DataHub OSS metadata and traces
  `logging_events.event_data` to `fct_users_created.user_name`.
- The product generates executable migration and regression SQL, a machine-readable
  impact file, a migration note, and a real Git commit.
- The reviewed decision is persisted through `save_document` and verified by
  reading its URN back through DataHub MCP.

## What we learned

The valuable primitive is not another catalog chat interface. It is translating
organizational metadata into a bounded, observable action while stating what the
metadata cannot prove. That same primitive can later power incident response,
training-serving parity, deletion planning, and other Luca tools.

## What's next

The next step is a CI check that receives a proposed schema diff directly from a
pull request, maps it to DataHub URNs, posts the impact summary on the PR, and
opens the generated compatibility patch for human approval. After proving that
workflow with users, Luca can expand into a suite without diluting the
focused ChangeSafe product.

## Built with

Python, FastAPI, DataHub OSS, DataHub MCP, SQLite, pytest, Git, GitHub Actions,
HTML, CSS, and JavaScript.

## Links

- Repository: https://github.com/Eienel/luca
- Live DataHub proof: use the most recent successful `live-datahub` workflow URL
  from the repository Actions page.
- Demo script: `docs/DEMO.md`

## Truthful demo claims

Say “every known consumer,” never “every consumer.” State that missing lineage or
query history remains unknown coverage. The system creates a review branch and
commit; it does not autonomously merge. The deterministic engine makes the safety
decision, while generated code still requires human approval.
