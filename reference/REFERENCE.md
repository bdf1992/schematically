# SOV Schematic 0.1 Reference

## Sentence

**Parts compose. Components contain. Wires connect.**

## Geometry

- Component boundary = closed line.
- Wire = open line.
- Part = named/addressable section of a line.
- Port = boundary/path Part that exposes an interface to a surface.

## Form

`Component → Form → Dimension + Body + Frame + Regions`

Dimensions:
- 0D Point
- 1D Path
- 2D Surface
- 3D Volume

An open interior Region may host other Components. Hosting changes relationship/scope, not Component implementation.

## Port reachability

- outside face → containing surface
- inside face → Component's interior surface
- both → both surfaces

A Wire is legal only if the endpoint exposure sets share a surface.

## Signals

- Source = active without upstream input
- On input = relay behavior
- Passive = does not originate packet flow

Packet travel rate in the current projection is:

`global time scale × source Component rate × Wire rate`

Packet skin remains source-Port identity; carrier/channel field may diffuse.

## Editor states

- Pin = geometry fixed
- Lock = immutable
- Hidden = omitted from canvas/hit testing but recoverable in Objects
- Opacity = projection only

## Classic examples

See `examples/`:
- `01-source-hold.sov`
- `02-duplex-buffer.sov`
- `03-contained-stage.sov`
- `04-boundary-port.sov`
- `05-rate-chain.sov`
- `06-read-write-evidence.sov`
- `classic-reference.sovpak`


## Direction, access, authority

These are separate axes:

- `direction` says how a signal crosses a boundary (`in`, `out`, `duplex`, `control`).
- `access` says what kind of interaction that Port/Connection permits (`none`, `read`, `write`, `read-write`).
- Wire packet `operation` says what the concrete crossing represents (`none`, `read`, `write`).
- authority is deliberately not inferred from any of the above.

A useful evidentiary reading is: a durable Record can receive a **Write** representing what happened, while an Observer/Witness can participate in a **Read** representing observation of what happened. This is representational semantics, not an authorization grant.
