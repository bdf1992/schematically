# Local core source dispositions

Audit date: 2026-10-11. These are source observations, not release qualification.
Acceptance owner: Bdo. Candidate task: schematically-sandbox-codex-sc.

| Surface | Observed identity | Disposition |
|---|---|---|
| Committed dev | 6649dc277e71f47d99b252685f9f23ba8b74ae86 | Base for the separate local candidate |
| Installed desktop | 0.1.0, executable dated 2026-09-02 | Exact embedded commit unknown; retain until candidate qualifies |
| Cloudflare build | 5622888813a07fcc83868028b47fc9017302da77 | Older public build; no public deployment in this effort |
| GitHub main | 9bebea1753297894f35e901278649044432ce952 | Selected desktop publisher/copyright/description metadata from c7959ca; other differences retained for disposition before landing |
| Open PR 169 | Remote Cloudflare Access listener | Separate web concern; excluded from local core |
| Canonical dirty source | 20 tracked changes and 10 untracked entries at audit | Preserve; not copied into the stable candidate |
| Unfinished Kore/ARCH cut | Later dirty work, failing descendant-start observation | Retain outside candidate; historical narrow passes do not qualify it |
| Interior zoom branch | 27c5170 | Retain experiment; overlaps renderer/layout/model |
| Axes branch | a2ee200 | Retain experiment; not installed or landed |
| N² branch | 6ca3253 | Retain experiment; not installed or landed |
| Wide Plane branch | 81d1096 | Retain; prior maker evidence needs independent qualification |
| Older wire/history work | 0fd18ad / 4805255 | Closed and superseded by landed PRs 156/160; unique commits do not prove missing behavior |
| Glyph asset work | 22515bf | Unique PNG asset; retain outside stable core |
| Rescue spike | b8b41dc | Retained abandoned evidence; no automatic cherry-pick |

The candidate adds native durable file effects and a live desktop MCP adapter;
the pre-existing Node MCP server remains a separate document owner. Documentation
ships as MCP resources in the desktop build. Knode/Kord consumers edit document
logic and code records and use declared runtimes; product source editing through
MCP is outside this release.

The release hold stays in place until supervised checks, architecture findings,
independent review, a real native MCP consumer and save/reopen evidence are
recorded against the candidate identity. No notes or unfinished source were
deleted during this audit.

Main-only QA artifact isolation commit6fa958c is not applied wholesale. Later dev
commit ea32d88 already isolates the affected suites and preserves newer checks.
Supervised legacy adapters must retain per-run artifacts outside source; the old
shared temporary directory and current-Git-status checker are not reinstated.

The expanded stable core requires modular declared runtime execution. Current
live MCP and bundled state-space runs do not establish external execution or
complete custom-definition authoring. These requirements remain release holds.
