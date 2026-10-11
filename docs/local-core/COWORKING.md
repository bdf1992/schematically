# Desktop co-working MCP

This entry point acts on the document open in Schematically's desktop editor.
Knode and Kord consumers use this endpoint when collaborating with the person
using that editor. The separate Node server described in MCP.md owns its own
stored document; it does not edit the desktop's live document.

## Discovery and connection

Each desktop process writes a descriptor under its Tauri local application data
directory, in `mcp/<pid>.json`. The descriptor provides `endpoint`, `token` and
`build`. Consumers select the intended process, retain the build identity and
send JSON-RPC 2.0 requests by HTTP POST with `Authorization: Bearer <token>`.
The address uses a random loopback port. Never publish the descriptor or token.
The process removes its descriptor on ordinary shutdown; a crashed process can
leave a stale descriptor, so connection failure requires fresh discovery.

Call `initialize`, then `notifications/initialized`, then `tools/list` and
`resources/list`. Documentation is bundled with the build; read
`schematically://docs/docs/local-core/COWORKING.md` through `resources/read`
or `schematic.documentation`. API.md, DATA-FORMATS.md, STATE-SPACE.md and
MODULES.md are available at corresponding `schematically://docs/` URIs.

The endpoint accepts one request at a time, with a 1 MiB body cap. Consumers
must bound their own connection deadline, treat HTTP 429 as busy, and avoid
blindly retrying a write whose response was lost. Read the live document and
history to determine whether that write took effect.

## Edit and save

1. Read `schematic.file.info` and `schematic.document.get`.
2. Retain `documentId`, `revision` and `stateToken` from file info.
3. Pass `documentId`, `ifRevision` and `stateToken` on each mutating tool call. Read again
   after a successful mutation. A document switch or conflicting edit refuses
   the stale request.
4. Use create, update, delete or apply for document edits. The batch tool uses
   the shared data core and the editor's history. Inspect receipts and markers;
   an HTTP success alone does not establish a successful tool operation.
5. Call `schematic.file.save` with the current guard values. An unassociated
   document opens a native Save As dialog for the person. Cancellation or a
   failed write does not establish a durable save. Confirm file info and retain
   the successful save result.

Saving is explicit. A successful edit can remain dirty in the desktop. Recovery
storage is separate from durable file save. Desktop MCP document replacement
uses the editor's replacement seam with history preservation and creates one
undoable entry. Ordinary file opening retains its existing history reset behavior.

## Custom logic and code

Code can be retained as data in reference records through reference CRUD.
Existing component logic fields can be inspected and updated. Component creation
does not preserve every logic/config field, and this candidate exposes no
definition-binding or custom-pack authoring operation. Those are qualification
gaps; generic CRUD success does not establish custom logic authoring support.
A validation refusal is a failed operation, not permission to rewrite the record
outside the shared core.

The local run tools execute the existing state-space runtime with its bundled
packs and return run handles, receipts and traces. They do not grant arbitrary
JavaScript, shell or filesystem execution. Code kept in a document is authored
data unless a declared runtime explicitly supports it. Extending executable
patterns or changing product source requires a separate source work contract,
architecture review and qualification before a rebuilt application is used.

The required stable core also includes modular declared runtime hosting: a
runtime may be hosted locally as a CLI process or by Schematically itself, or
delegate to a declared external provider. The first increment implements one
Node CLI provider. It remains under qualification; provider admission, limits,
cancellation and durable results must pass before a release is accepted.

### Node CLI provider

The desktop host reads `providers.json` beneath its local application data
`runtime` directory. A host may select an absolute directory through
`SOV_RUNTIME_DIR`, including an isolated qualification directory. MCP tools cannot
change this configuration. Missing configuration admits no execution.

Configuration uses schema `schematically.cli-host@1`. The admitted provider is
`node-cli`, version `1`. A provider has `id`,
`version`, `language: "javascript"`, an absolute canonical `executable`, its
`executableSha256`, and `limits`: `timeoutMs`, `maxOutputBytes`, `maxProcesses`,
and `maxMemoryBytes`. The executable is the host's trusted Node runtime. Its
arguments are fixed: `--unhandled-rejections=strict` and the frozen module path.
Limits restrict process lifetime, combined captured stdout/stderr, process count
and committed memory. Job containment does not isolate filesystem or network
access; a grant authorizes trusted code under the local user's account.

A separate grant has `id`, `providerId`, `providerVersion`, `documentId`, exact
`sourceHash`, `requestId` and `expiresAtUnixMs`. It admits one matching attempt.
MCP authentication and provider registration supply no grant. The host retains
grant consumption before execution. Repeating the same request and frozen
identities reads its retained attempt; changing them refuses. An interrupted
attempt with unknown completion is never executed automatically again.

Create a reference with `kind: "code"` and this `data`:

```json
{
  "schema": "schematically.code@1",
  "language": "javascript",
  "source": "import fs from 'node:fs'; const input = JSON.parse(fs.readFileSync(0, 'utf8')); console.log(JSON.stringify({value: input.value + 1}));",
  "sha256": "<SHA-256 of the exact UTF-8 source>"
}
```

The module receives serialized JSON input on stdin. stdout and stderr are retained
separately within one output limit; output is data, without an automatic document
edit. `schematic.runtime.providers` lists registered identities and limits.
`schematic.runtime.start` takes `requestId`, `providerId`, `providerVersion`,
`grantId`, `referenceId`, `codeHash`, `input` and the current `documentId`,
`ifRevision` and `stateToken` from `schematic.file.info`. It freezes the reference
source and input, verifies their hashes and returns an attempt receipt promptly.

`schematic.runtime.status` and `schematic.runtime.results` take `requestId` and
the active `documentId`. Results require a recorded terminal receipt with verified
descendant cleanup. `schematic.runtime.cancel` additionally takes current revision
and state guards. Receipts retain document/revision/state, reference/code/input,
provider/executable/grant identities, outcome, exit code, output hashes and cleanup
evidence. A later ordinary guarded document edit can accept a result.

The host runs one active attempt and retains at most 64 attempts. It records intent
before creating a suspended process, assigns a kill-on-close Windows Job Object
before resume, and refuses containment failure. Timeout, cancellation, output
overflow and application shutdown terminate the job and check descendants before
recording completion. A recording or cleanup failure remains an unresolved result.

Knode and Kord integrations should record the selected desktop build, document
identity, observed revision, operation, receipt and resulting saved state.
Their task ownership and execution authority remain with those consumers;
connecting to Schematically does not transfer either authority.

## Qualification state

This interface is a release candidate. Native transport, lifecycle, access
permissions and consumer compatibility must pass retained qualification before
the local release hold is removed. Discovery, schemas and descriptions are not
evidence of those runtime results.
