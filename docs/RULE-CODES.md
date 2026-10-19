# Rule codes

Every finding from `node scripts/validate_sov.mjs --json`, `python scripts/deliver_sov.py` and the MCP tool
`schematic.deliver` carries one of these codes. A code is stable: it is never renumbered or reused, and a code
that stops being reported stays listed. The table they come from is `scripts/sov_rules.json`;
`tests/deliver_qa.py` fails when this page and that table list different codes.

A finding is `{code, family, severity, id, rule, detail, message, repair}`. `id` is the component, wire or
reference the finding names, else the document id. `detail` is the validator's own upper-case code when the
message carries one (for example `GROUP_MEMBER_TWICE`). `rule` is the marker rule `schematic.markers` reports
for the same message, null for load and render findings. `repair` is the suggestion below with the id and detail filled in.

An `error` refuses delivery and leaves the previous viewer untouched; a `warning` never refuses.

## Load: the file is read and opened as a document.

| Code | Severity | Finding | Repair |
| --- | --- | --- | --- |
| SOV101 | error | file cannot be read | Check the path; the file must exist and be readable. |
| SOV102 | error | file is not JSON | Fix the JSON syntax at the position the message names; a .sov is one JSON object. |
| SOV103 | error | payload is not an object | Wrap the document in one JSON object with "schema", "components", "wires" and "references". |
| SOV104 | error | file schema unsupported | Set "schema" to the document schema (see GET /api/v1/formats, field document). |
| SOV105 | error | package refused | The package's inner document failed; fix the errors listed in the message, which are the document's own. |
| SOV106 | error | document refused at load | The loader refused the document before validation; fix what the message names (the same refusal the editor gives on open). |

## Schema: the document's own fields.

| Code | Severity | Finding | Repair |
| --- | --- | --- | --- |
| SOV201 | error | document schema mismatch | Set "schema" to the value the message names. |
| SOV202 | error | document shape | Give the document "components", "wires" and "references" as arrays (empty is allowed). |
| SOV203 | error | record has no id | Give every component, wire and reference a non-empty "id". |
| SOV204 | error | duplicate id | Rename one of the records called {id}; ids are unique per kind. |
| SOV205 | error | narration malformed | Write narration as an array of {"at": <tick>, "say": "..."}; every line needs a say string. |
| SOV206 | error | time scale invalid | Set meta.timeScale to a finite number >= 0, or remove it. |
| SOV207 | error | palette invalid | Set meta.palette to a known palette name (the message lists them) or {"custom": [six "#RRGGBB" hexes]}, or remove it. |
| SOV208 | error | section bands do not fit lines | On {id}, give form.section exactly one band fewer than it has lines. |
| SOV209 | error | card shape invalid | On {id}, use a card shape the message lists, or remove the shape. |
| SOV210 | error | badge invalid | On {id}, correct config.badge as the message says, or remove it. |
| SOV211 | error | intake invalid | On {id}, correct the intake field the message names, or remove it. |
| SOV212 | error | declared ports invalid | On {id}, correct the declared ports the message names; a port still carrying a wire cannot be removed. |
| SOV213 | error | virtual definition invalid | Correct the virtual definition or instance on {id} ({detail}) as the message says. |

## Wires: ends, surfaces, channels and operations.

| Code | Severity | Finding | Repair |
| --- | --- | --- | --- |
| SOV301 | error | wire end names no component | On wire {id}, point the end at an existing component id, or create that component. |
| SOV302 | error | wire ports share no channel | On wire {id}, attach the ends to ports that share a channel, or give one port the other's channel. |
| SOV303 | error | wire crosses a boundary | On wire {id}, route through a port the boundary exposes, or move both ends onto one surface. |
| SOV304 | error | wire canvasId disagrees with its ends | On wire {id}, set "canvasId" to the surface the message names, or remove canvasId so the loader derives it. |
| SOV305 | error | wire end has no surface | On wire {id}, attach the end to a component port or attachment point that exists on a reachable surface. |
| SOV306 | error | wire operation invalid | On wire {id}, set forwardOperation and reverseOperation to none, read or write. |
| SOV307 | error | wire kind not declared | On wire {id}, use a wire kind the notation declares, or declare it in the notation. |
| SOV308 | error | path delay invalid | On {id}, set the delay to a whole number of ticks >= 0, or remove it. |

## Notation: the notation, its statuses and its concerns.

| Code | Severity | Finding | Repair |
| --- | --- | --- | --- |
| SOV401 | error | notation does not resolve | Name a notation that exists, or correct the scale or glyph size the message names. |
| SOV402 | error | notation kind rule broken | In the notation, correct the kind entry the message names. |
| SOV403 | error | notation concern rule broken | In the notation, correct the concern entry the message names. |
| SOV404 | error | status not declared | On {id}, use a status the notation declares, declare it in the notation, or remove config.status. |
| SOV405 | error | waits-on invalid | On {id}, write config.waitsOn as a list of {"kind": person\|rule\|decision, "id": "..."}. |
| SOV406 | error | concern answer invalid | Answer only concerns the notation declares for {id}, each with a non-empty string ({detail}). |

## Groups.

| Code | Severity | Finding | Repair |
| --- | --- | --- | --- |
| SOV501 | error | group membership invalid | Fix group {id} ({detail}): every member exists once, sits on the group's canvas, and is not itself a group or hosted. |

## Render: checked by `scripts/deliver_sov.py` in headless Chromium, after the document passes the checks above.

| Code | Severity | Finding | Repair |
| --- | --- | --- | --- |
| SOV601 | error | editor failed while drawing | The editor raised an error opening or drawing the document; the message holds it. Open the file in the editor to see the same error. |
| SOV602 | error | picture is empty | The light or dark picture came out empty; check that the document has placed components on its default layout. |
| SOV603 | error | viewer shows another document | The viewer's id or card count differs from the checked file; the editor refused the file and kept another. Open it in the editor to see why. |
| SOV604 | error | renderer unavailable | Install Playwright Chromium (python -m playwright install chromium) and build index.html (python build.py). |
| SOV605 | warning | wire blocked for tracing | Wire {id} is drawn but tracing does not follow it ({detail}); expected for an access-blocked wire, otherwise open its direction or access. |

## Write: the checked viewer replaces the target.

| Code | Severity | Finding | Repair |
| --- | --- | --- | --- |
| SOV701 | error | viewer could not be written | The checked viewer could not replace the target (the message names why: read-only, in use, or a folder of that name); free the target path or choose another --out. |

## Unclassified.

| Code | Severity | Finding | Repair |
| --- | --- | --- | --- |
| SOV999 | error | unclassified finding | The validator reported a message no rule code covers yet; fix what it says and file the message so a code can be added. |
