---
name: schematically
description: Turn a description, a plan or a codebase into an interactive diagram that opens in any browser. Cards and wires are checked against a semantic model (boundaries, ports, direction, read/write access), laid out automatically and delivered as one HTML file with search, downstream/upstream tracing, routes, a type lens, an overview map, four styles, light/dark, a presentation mode, PNG and share cards. Use when asked to diagram, map, draw, chart or visualise a system, service, request flow, architecture, pipeline or plan.
---

# Schematically

You write a small `.sov` document (JSON: cards and the wires between them) and run one command.
The command checks the document with the same data core the Schematically editor runs, lays it
out when you gave no coordinates, and writes one `.html` file the reader opens from disk. Node 18
or newer is the only requirement.

```
node <skill>/bin/schematically.mjs deliver diagram.sov --open --json
```

`<skill>` is the folder this SKILL.md is in. On Windows pass Windows paths (`C:\...`) to `node`.

## Steps

1. Decide what the diagram is for and its scope before drawing: the one path a reader should
   follow first, then what feeds or watches it. Eight to twelve cards is a good first diagram.
2. Write `<name>.sov` in the user's working directory in the form below. Leave out `x` and `y`:
   the layout engine places cards left to right along the wires.
3. Run `deliver` with `--json`, and with `--open` when the user is at this machine's screen.
   The `.html` is written beside the `.sov` unless you name another path after it. On
   `{"ok": true}` tell the user the `target` path (it opens from disk in any browser) and what
   the diagram shows; `laidOut` says the layout engine placed the cards.
4. On `{"ok": false}` read each finding's `code` (a stable `SOVnnn`), `id` (the card or wire it
   names), `message` and `repair`, apply the repair to that record, and run again. After two failed rounds, stop and show the user the
   diagnostics rather than guessing further.
5. For a change ("add auth", "the cache is optional"), edit the same `.sov` and deliver again. A
   failed run leaves the last good `.html` in place.

`node .../bin/schematically.mjs demo [dir] --open` writes and delivers a four-card example.
`validate file.sov --json` checks without writing anything.

## The document

```json
{
  "schema": "soveraeign.schematic/document@0.1",
  "id": "checkout",
  "revision": 0,
  "meta": {"title": "Checkout request path"},
  "components": [
    {"id": "web", "symbolId": "act", "config": {"label": "Web app", "signalMode": "source", "note": "React SPA"}},
    {"id": "api", "symbolId": "act", "config": {"label": "Checkout API"}},
    {"id": "auth", "symbolId": "authority", "config": {"label": "Session token"}},
    {"id": "db", "symbolId": "hold", "config": {"label": "Orders DB"}}
  ],
  "wires": [
    {"id": "w1", "a": "web", "aSide": "out", "b": "api", "bSide": "in", "config": {"label": "POST /checkout"}},
    {"id": "w2", "a": "auth", "aSide": "out", "b": "api", "bSide": "control", "config": {"label": "permits"}},
    {"id": "w3", "a": "api", "aSide": "out", "b": "db", "bSide": "in", "config": {"label": "insert order", "forwardOperation": "write"}}
  ],
  "references": []
}
```

- Ids are short, unique and stable: wires and later edits refer to them.
- `config.label` is what the reader sees; keep it to a few words. Put the explanation in
  `config.note`, which opens when the reader clicks the card.
- A card has three attachment points: `in` on the left, `out` on the right, `control` on top. A
  wire runs from `a`/`aSide` to `b`/`bSide`. Feed permission or configuration into `control`.
  Tracing downstream does not follow control wires.
- Wire `config`: `label`; `direction` (`forward` default, `reverse`, `duplex`); `forwardOperation`
  `read` when the `a` card reads from the `b` card, `write` when it writes to it. Direction and
  access describe; they never grant.
- Draw each wire the way the request or data travels. A reply may be a wire back to the caller;
  cycles are fine. Draw one wire per pair of cards: two wires between the same two cards are drawn
  on top of each other, so fold them into one label ("read, fill on miss") or route one through
  another card.
- A decision (cache hit or miss, approved or refused) is a `gate` card with one wire out per
  outcome, each labelled with its outcome (`"hit"`, `"miss"`).
- Mark the card where the story starts with `"signalMode": "source"`.
- `revision` stays `0` and `references` stays `[]`; both are for the editor.

## Card types (`symbolId`)

| symbolId | Use it for |
| --- | --- |
| `act` | A service, process or step that does work. The default choice. |
| `hold` | A store: database, cache, queue at rest, file. |
| `buffer` | Something that holds flow and releases it: a queue, a batch. |
| `gate` | A check that passes or refuses: validation, policy, rate limit. |
| `switch` | A path opened or closed by an explicit control. |
| `observe` | Reads without acting: monitoring, logging, analytics. |
| `receipt` | Durable evidence an action leaves: an audit record, an event. |
| `authority` | A permission or credential fed into a `control` point. |
| `refuse` | An explicit dead end: a rejected request. |
| `join` | Paths that merge. |

## Boundaries (optional)

To show a trust boundary or a deployment unit, add a `plane` and put cards inside it with
`"parentId": "<plane id>"` and `"canvasId": "canvas:component:<plane id>"`. A wire cannot cross
a boundary on its own: it needs a `point` on the plane's edge with face `both`, and two wires,
one on each side. Planes and boundary points need coordinates, so write `x`/`y` for every card
when you use them:

```json
{"id": "svc", "symbolId": "plane", "x": 640, "y": 360,
 "form": {"dimension": 2, "regions": {"interior": {"state": "open"}}},
 "config": {"label": "Private network", "attachmentDefaults": "none",
            "presentation": {"graphic": {"kind": "none"}, "size": {"w": 480, "h": 230}}}},
{"id": "ingress", "symbolId": "point", "x": 400, "y": 360,
 "canvasId": "canvas:component:svc", "parentId": "svc",
 "placement": {"kind": "edge", "hostId": "svc", "side": "left", "t": 0.5},
 "config": {"label": "ingress", "ports": {"out": {"face": "both"}}}}
```

A wire from outside ends at `"b": "ingress", "bSide": "out"`. The wire inside starts at
`"a": "ingress", "aSide": "out"` and carries `"canvasId": "canvas:component:svc"`. Coordinates are
the card's centre, in canvas units; a card is about 112 by 84, so leave about 200 between centres.

## What the reader gets

One `.html` file, about 500 KB, that works offline and asks the network for nothing. Readers can:
search with `/`; click a card to see its note and links; trace downstream (`d`) or upstream (`u`);
find the shortest route between two cards (`r`); pick out one or two card types with the lens
(`l`); move around a large drawing with the overview map (`m`); switch style (`s`: Clean, Notes,
Glass, Circuit) and light/dark (`t`); present the diagram card by card (`p`); save a PNG, a
1200×630 share card of a traced route or reach, or print to PDF; and copy a link that restores the
current view (`#style=glass&theme=dark&present=1`, `#focus=api&mode=down`, `#lens=act~hold`). The same `.sov` opens in
the full Schematically editor (https://github.com/bdf1992/schematically) for direct editing and
simulation.
