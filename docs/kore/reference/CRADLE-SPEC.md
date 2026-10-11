# The Cradle: an engine for raising agency

Specification, second edition, 2026-10-01. Status: draft for the originator's reading.

Sources: the cradle board dossier in this folder (`01-host-pieces-and-rounds-1-2.md`, `02-rounds-3-4.md`), the originator's four messages and four rounds of a nine-seat board, and the originator's correction to the first edition: the cradle is a neutral engine, and every opinion is content that people author and load into it. Where this text makes a call that neither the board nor the correction settled, it says so and marks it as the writer's reading.

---

## 1. Summary

A cradle is a neutral engine for procedural work: it holds state as a graph of entities and relations, runs transitions on that state, records every transition with the situation it happened in, and answers questions over that record. It knows nothing about any domain and holds no opinions. Everything opinionated (what kinds of work exist, what counts as a spill, how bad a spill is, which situations are alike, what an occupant may do and how that widens or narrows) is content: data written by named authors (designers, parents, guardians) and loaded into the engine, which holds, versions, applies and records it. Authors work the cradle through the same doors as everyone else, and their acts are recorded like any other transition. Into a cradle proven with nobody in it, an occupant (usually an AI agent) is brought and raised: it acts, the engine records what happened, and the authors' content reads that record to decide what the occupant may do next, in each situation. The race-car bed, the full working harness, is the same cradle with content that has taken many guardrails off. The pattern ships as a baby box: the engine, a record format, and a guide that advises authors what content to write as raising goes well or badly.

---

## 2. The paradigm

The cradle separates the engine from the game. A game engine runs physics, state, time and replay and knows nothing about the game; designers author levels and rules as data, and the engine runs whatever is loaded. The cradle applies that split to raising agency. The engine is the cradle. The opinions about how to raise an actor live with the people who hold them, and enter the cradle as authored content.

Underneath the split is a relationship: guardianship, lived as a lifecycle. Trust is extended to a new actor only as fast as witnessed experience accumulates, and only in the circumstances where it happened. The engine carries the facts of that relationship (what happened, where, under which rules); the authors carry its judgements (what that means for freedom). Neither does the other's job.

Stated without any technology:

1. The place comes before the occupant. The engine, and then the content for a piece of work, run and are proven with nobody being raised in them.
2. The place holds no opinion. It records and applies; people judge, and their judgements are content with an author and a version.
3. What happened is kept by the place, not by the one judged. No actor writes the record directly, the occupant included.
4. Every freedom can be explained from the record and the content in force.
5. Trust is situated, moves both ways and grows by loosening the same place towards handing over. These are what good content does; the guide recommends them, and the engine makes them possible.

**Human precedents.** Raising a child: the cot is safe before the baby arrives, and the household, not the cot, decides when the three-year-old may pour juice alone. The Finnish maternity package: one standard box and a booklet for one need, given to anyone. Apprenticeship: the master signs the logbook. Medical residency: a resident is entrusted with a named procedure on a named ward from observed performance (formalised as entrustable professional activities; writer's addition). Aviation type ratings and recency rules: trust per aircraft type, renewed by recent practice (writer's addition).

**Technical precedents.** Game engines and data-driven design, where levels, rules and balance are content and designer edits are versioned; entity-component systems. Policy engines that separate the point where a rule is decided from the point where it is enforced, with rules loaded as data and every decision logged (writer's addition, from policy-as-code practice). Event sourcing, where state is rebuilt from a log. Reinforcement-learning environments, which fix world and actions before the policy. Earned privileges on community platforms (Discourse trust levels, Stack Overflow tag privileges), which also show that rules built on raw counts get farmed. Progressive delivery, shadow mode and staged driving autonomy, which widen freedom per operating domain from logged outcomes. Christopher Alexander's pattern language, which is the shape of the guide.

---

## 3. Layers and roles

The cradle is kept in three layers, on a seat, with three kinds of participant.

```
seat              the station the engine runs on: host, tools, services, hours (observed)
  engine          the cradle: state graph, transitions, record, queries. No opinions.
    content       authored rules and readings, loaded as data; versioned; each with a named author
guide             outside the engine: advice to authors on what content to write, by situation
```

**Seat.** The station the engine runs on: host, tools and their versions, dependencies, credentials, outside services, hours. The engine observes the seat and records it with every transition. The same content on a different seat runs in different conditions.

**Engine.** The cradle proper. It provides, for any domain: a state graph of entities and relations; transitions on that state, entered through doors (the only ways to change state); a record of every transition; the loading and versioning of content; the application of whatever content is in force; and queries over the record. Its behaviour does not depend on any domain.

**Content.** Everything opinionated, as data: encounter kinds, the definition of a spill, severity functions, similarity rules between situations, thresholds, guardrails, the reserved set, and the rules by which freedom widens and narrows. Each piece has a named author and a version. Content is loaded by a transition, so loading it is recorded. One cradle with its content is the game a parent or designer builds on the engine.

**Guide.** Advice to authors: what content to write, and how to change it, according to how raising is going. The guide is not loaded into the engine.

**Occupant.** The actor being raised: an agent, a model version, a sub-agent, a new person, a service. It acts through the engine's doors under the content in force.

**Author.** Anyone who writes content: a designer, a parent, a team, a guardian. Authors act through the same doors as any participant, and their acts are transitions in the record.

**Guardian.** An author who reads the record of an occupant and changes content to widen or narrow that occupant's freedom. The guardian is a role people (or outside agents) hold, not a part of the engine. It stands outside the occupant: it does not do the occupant's work, and it is not the occupant.

**Witnessing** (establishing what happened without asking the occupant) is the engine's mechanical job: every transition goes through its doors, so it sees the change to state itself. Judging what that means is the guardian's.

---

## 4. Concepts

**Encounter.** One meeting between the occupant and a piece of work: the transitions it made, their inputs, outputs and changes to state, and the situation. The originator also calls these reps. Which transitions make up one encounter, and of which kind, is defined by content.

**Situation.** The observed conditions of a transition: the seat as it was, the relevant state, tools and versions, the time and the condition of outside services. The board called this context. The engine records it; content decides which situations are alike.

**Spill.** An encounter whose outcome fell short, found at once or later. The change to state is a fact the engine recorded. The rule that classifies a change as a spill is content. Applying that rule to that change is mechanical and reproducible, so a spill is not anyone's say-so: it follows from the record and a named, versioned rule.

**Severity.** How bad or good an outcome was, as a scalar, computed by an authored severity function over the recorded change. The same reasoning as for spill applies.

**Agency.** What this occupant may do, in this cradle, in this situation, now. It is the result of applying the content in force to the record. It is never stored apart from those two, so it can always be rebuilt and explained.

**Guardrail.** One limit in content on what the occupant may do. Raising removes guardrails; narrowing puts them back. Both are content changes, recorded as transitions.

**Race-car bed.** The cradle at the stage where content has taken many guardrails off for the situations the occupant has proven. Same engine, same record, fewer rails.

**Baby box.** What the pattern ships as: the engine, the record format, a reference cradle with sample content, and the guide.

---

## 5. Engine invariants

The engine guarantees these, whatever content is loaded, including none. Under each is what breaks without it.

**E-1. One way in.** Every change to state is a transition through the engine's doors, attributed to the actor who made it. No actor (occupant, author, script or operator) writes state or the record by any other path.
*Without it:* the record is no longer the whole story, and an actor can make its own history.

**E-2. Every transition recorded with its situation.** Each transition is recorded with actor, inputs, outputs, change to state, the content versions in force, and the observed situation. A transition whose record would be incomplete is refused, not defaulted.
*Without it:* trust cannot be situated, because the record does not say where anything happened.

**E-3. The record only grows.** Recorded transitions are not edited or removed through the engine; a correction is a new transition pointing at the old one.
*Without it:* a late spill can be erased instead of reaching back.

**E-4. Content is data, versioned and attributed.** Every rule the engine applies is content loaded by a recorded transition, with a version and a named author. The engine contains no domain rule of its own, and it applies whatever version is in force, the same way for every actor.
*Without it:* opinions hide in the engine's code, which is what a harness does today, and no one can see or own them.

**E-5. Rebuildable.** State, including every actor's agency, can be rebuilt from the record and the content versions it names. Where a transition is not deterministic, the source of nondeterminism is recorded with it.
*Without it:* agency becomes a stored grant that can outlive its reasons, and rule changes cannot re-read history.

**E-6. Explainable.** For any permission or refusal, the engine answers from the record alone: which content rule, at which version, by which author, applied to which transitions in which situations, produced it.
*Without it:* nobody can say why an occupant may do this here, which is the question the cradle exists to answer.

**E-7. Absence is refused.** A transition that no content in force permits is refused, and the refusal is recorded. With no content loaded, the only transition the engine accepts is the first content load, which becomes the first entry in the record under its author's name (E-Q1); no occupant may do anything. (Writer's reading: the correction does not say what the engine does when no rule applies. Refusing is the only behaviour that adds no opinion of its own, and it is what makes the empty engine testable.)
*Without it:* the engine's defaults become an unauthored opinion about what an occupant may do.

---

## 6. Content conventions

These are what the board agreed good content does. The engine does not enforce them, because each is an opinion; it makes each one writable and checkable. The guide recommends them.

**C-1. Trust is situated.** Content grants agency per kind of work and per situation, and lets experience count in another situation only through a written similarity rule. Context is part of what the trust is, not a tag added later. Without this, agency travels as a credential and juice reps unlock coffee.

**C-2. Experience, not volume.** Content weighs encounters by difficulty and variety; retries of one encounter count once; many near-identical easy encounters count little. Without this, occupants farm easy reps (forty thimbles to earn the jug).

**C-3. Spills outweigh passes, and late spills reach back.** Content narrows on a spill by more than a clean encounter widens, and a spill found later discounts the encounters that hid it.

**C-4. Narrowing does not wait for a hearing.** Content narrows at once on a severe spill, a change of seat or situation, a change of occupant, or a change to the cradle's content.

**C-5. Reserved actions.** Content declares a set of actions that do not loosen by record alone: actions that cannot be undone, that touch other people, or that are matters of taste. Their loosening is an author's recorded act.

**C-6. What an occupant writes about itself takes effect through other rules.** An occupant may write or change content that governs it, as recorded transitions under its own name; the engine accepts it like any author's. Whether it takes effect is decided by content the user writes, for example: content an occupant writes about itself takes effect only after a person approves it. Without such a rule, an occupant could widen its own freedom with nothing but the record to show it happened. (Answered 2026-10-01; see E-Q2.)

**C-7. Growth is loosening the same place, towards handing over.** Content removes guardrails in the same cradle, and is judged by whether freedom grew where the record supported it, not only by what it prevented.

**C-8. Cost below the trust it buys.** A cradle and its content cost less than doing the work by hand or by a fixed script. Where they do not, staying manual is a valid result.

---

## 7. Lifecycle

**7.1 Empty engine.** The engine runs with no content and no occupant and passes the engine requirements (Section 11.1). This is what proven with nobody in it means at the engine level: every check is made with no opinionated content loaded, using neutral test fixtures (entity and transition types that carry no domain meaning).

**7.2 Empty cradle.** Authors load content for one kind of work on one seat, and the work runs through the cradle with no occupant being raised: by scripts or people, end to end. The record shows the baseline: how the work goes, how often it spills and what the cradle costs, with nobody in it. The guide recommends not admitting an occupant until this baseline exists.

**7.3 First occupant.** An occupant enters with its identity recorded. Its agency is whatever the newcomer content says: typically shadowing (it proposes; the existing means acts) or acting behind every guardrail.

**7.4 Raising, loosening, narrowing.** The occupant acts; the engine records; guardians read the record and change content to widen or narrow agency. Each content change is a transition and names the evidence it rests on. Narrowing rules written in advance act at once when their conditions appear in the record.

**7.5 Handing over.** For situations the occupant has proven, content takes the guardrails off and the occupant works unattended there. The record keeps running and narrowing stays possible. Later, a raised occupant may become an author and guardian of content for a new occupant in another cradle, proven empty first; whatever it writes about itself takes effect only as the user's content allows (C-6).

**Re-reading the first edition's three calls.**
- *Witness and guardian as one role:* changed. Witnessing is the engine's mechanical recording; the guardian is an author and reader of content, outside both the engine and the occupant.
- *Agents building the race-car bed:* holds in a new form. An occupant works the cradle through the same doors as anyone; whatever it builds or proposes (a tool, a content change) is a recorded transition. Whether it may adopt content, and whether a change re-runs the empty-cradle baseline, are content and guide matters, not engine guarantees. What no actor can do, by E-1 and E-3, is write the record directly.
- *Handing over and sub-agents:* holds, moved from invariant to guide, and changed on 2026-10-01: a raised occupant may author and guard content for a new occupant in a new cradle, and may also write content about itself, which takes effect only as the user's content allows (C-6). This remains the reading of the originator's point that there should be no sub-agents until an agent can raise them.

---

## 8. The record format (the protocol)

The record format is what makes cradles interoperable and what any engine must produce. It has three record types.

**Transition record.** Identity (stable, so a retried or replayed transition is recognised); actor; entities touched; inputs; outputs; change to state; the observed situation; the content versions in force; whether it was permitted or refused, and by which rule; any pointer to an earlier record it corrects or relates to.

**Content record.** The content itself as data; its kind (encounter kinds, spill rule, severity function, similarity rule, threshold, guardrail, reserved set, widening or narrowing rule); its version; its author; the transition that loaded it; what it replaces.

**Derived reading.** The result of applying a content rule to records (a classification as spill, a severity, an agency): rule and version, the records it was applied to, the result. A derived reading can always be recomputed and must match.

**Queries every engine answers** from the record alone:
1. Why may this actor do this here, now? Why may it not?
2. Which transitions, in which situations, does this permission rest on, and would it survive if one of them were later classified a spill?
3. Which content, at which version, by which author, produced this permission or refusal?
4. What changed this actor's agency last, and which transition did it?
5. Which situations has this actor met, and which never?
6. Who authored each rule in force, and when was it loaded?
7. What did this cradle do with no occupant, and what has the occupant changed against that baseline?
8. What has the cradle cost per transition and in total?

**Between cradles.** An occupant's record moves between cradles (people, teams, federation members) as evidence, never as agency. The receiving cradle's content decides what, if anything, counts there.

---

## 9. The guide

The guide is advice to authors on what content to write and when to change it, arranged by how raising is going. It is the pattern part of the baby box: there is no right way to raise agency, and there is a good deal of known advice about raising it badly.

**Before the first occupant.** Push placeholder work through the whole cradle and look at what comes out. Write encounter kinds and the spill rule before any occupant exists, and name who owns each. Measure the cradle's cost against the work; don't build a cradle for work a cron job and a checklist already carry. Don't let the first occupant finish building the cradle.

**Raising is going well.** Check variety: are clean encounters spread across situations, or bunched in easy ones? Keep reading after loosening. Don't loosen a reserved action because a count is high.

**Spills are happening.** Write narrowing rules that act at once on severe spills; argue meaning afterwards. Look for late spills (outputs that looked fine at intake and failed downstream) and make them reach back. Count retries as one encounter.

**The situation changed** (new seat, new tool, a service down, a different hour). Treat it as unproven until a similarity rule covers it. Test similarity rules against later outcomes and split situations that spill at different rates.

**The occupant changed** (new model, instructions, tools, a copy). Decide from evidence how much history still applies, and write that as content. Don't let copies pool their records.

**Raising has stalled.** Check whether content is judged only on prevention, and whether the reserved set has grown to cover everything. Accept that some steps never earn trust; keep them scripted or human.

**Handing over.** Keep the record running after guardrails come off. Let a raised occupant author content for a new one, in a new cradle. When an occupant writes rules about itself, have them take effect through an approval rule you wrote.

**Authoring questions.** Some questions the board left open are now questions every author answers in content. The guide carries the board's positions so authors can choose:
- *Who judges that two situations are alike.* Declare it and version it (distributed systems, engine, platform); declare it, then test it against later outcomes and split situations that spill differently (ML, the middle path the board recorded); derive it from the cradle's own structure and outcomes, checked by a person (graph, procedural); or treat it as a guardian's judgement that must not be hidden in a formula (skeptic). The engine seat doubted that declaring once is enough.
- *Thresholds and how freedom moves.* A lower confidence bound on success per kind and situation with a cap on severity (ML; 20 passes in 20 has a one-sided 95% lower bound near 0.86); counts weighted by novelty (skeptic, procedural); human decision for the top step with automatic narrowing (skeptic, after Discourse); whether a spill drops a whole level or is weighed against clean encounters (engine, unsettled).
- *Identity of an occupant after change.* Tie agency to the exact model, instructions and tools and reset on change (harness, distributed, skeptic); or make it the guardian's evidence question, not a hash comparison (platform, round 4).
- *Whether a record beats judgement.* Asset and platform asked for data that per-kind records predict the next spill better than a reviewer's sign-off; the skeptic doubted any rep definition survives real traffic without retuning; the harness seat wanted a red-team run over real time before loosening by record alone. These remain hypotheses for content authors to test.

**Why the guide matters.** Several seats argued the guide and a catalogue of encounter kinds are where most of the value lies: counting is generic, but defining kinds and spills for a domain is the hard part, and studios found the onboarding runbook mattered more than the template. The procedural seat's counterweight stands: a guide with no running reference cradle drifts. The baby box carries both.

---

## 10. Why a harness wants to be this

An agent harness today mixes engine and opinion in one body of code: tool access, retries, approval prompts, what counts as done and what the agent may touch are written into the harness and change when someone edits it. Nobody can say from evidence why the agent may do something, the rules change without a record, the agent's own report often stands in for what happened, and trust is set once and applies everywhere.

The cradle separates the two. The engine is the part every harness rebuilds (state, transitions, a record, permissions checked at one door, queries), done once and kept neutral. The opinions are content, authored by named people, versioned and recorded when they change. A harness built this way can answer why an agent may do this here, can take freedom back when conditions change, and can take a new model without rewriting its code: the new occupant enters, and the content decides how much of the old record applies. Game engines made the same move when the world stopped being written into each game.

---

## 11. Requirements

### 11.1 Engine conformance requirements

Each is checkable with no opinionated content loaded, using neutral fixtures. Passing all of them is what proven with nobody in it means for an engine.

- **ER-01 One way in.** Attempt to change state or the record other than through a door; it fails, and the attempt is recorded where the engine can observe it.
- **ER-02 Complete records.** Submit a transition without its situation; it is refused and the refusal recorded.
- **ER-03 Append only.** Attempt to edit or delete a recorded transition through any door; it is refused. A correction appears as a new transition linked to the old.
- **ER-04 Content attributed and versioned.** Load content without an author or version; it is refused. Load two versions; the record shows which was in force for each transition.
- **ER-05 No built-in domain rule.** With no content loaded, every occupant transition is refused and recorded, and the first content load is accepted as the first entry in the record, under its author's name.
- **ER-06 Same doors for all.** An author's content load and an occupant's action appear in the record in the same form, each attributed.
- **ER-07 Rebuildable.** Rebuild state and agency for a past moment from the record and named content versions; it matches what was in force. Replay a transition N times; its identity makes it count once.
- **ER-08 Re-reading.** Load a new version of a fixture rule; derived readings over past records can be recomputed under it, and the old readings remain on record.
- **ER-09 Explainable.** Pick any permission or refusal from a fixture run; the engine answers queries 1 to 6 of Section 8 from the record alone.
- **ER-10 Situation recorded.** Change one observed seat condition; transitions after the change record the new situation.
- **ER-11 Cost observable.** The engine reports its own cost per transition and in total.
- **ER-12 Format.** The engine exports its record in the record format of Section 8, and another engine can rebuild the same state from it.

### 11.2 Guide recommendations for content

Each is a check an authored cradle could fail. They test content, so they are recommendations, not engine conformance.

- **GR-01** An empty-cradle baseline exists before the first occupant enters (7.2).
- **GR-02** Agency is scoped by kind and situation; an unseen situation gives newcomer agency (C-1).
- **GR-03** Experience transfers only through a written, owned similarity rule (C-1).
- **GR-04** Many near-identical easy encounters earn visibly less than varied ones (C-2).
- **GR-05** A late spill narrows agency resting on the encounters it discounts within a stated time (C-3).
- **GR-06** A severe spill, a seat change or an occupant change narrows agency within one cycle without waiting for a person (C-4).
- **GR-07** Reserved actions do not loosen by record alone (C-5).
- **GR-08** Content an occupant writes about itself takes effect only as other content the user wrote allows (for example, after a person approves it); for every rule in force, the record shows its author and any approval (C-6).
- **GR-09** Copies of an occupant do not pool records.
- **GR-10** Situations where agency was widened show a later spill rate within the bound stated when they were widened (calibration).
- **GR-11** The cradle shows where guardrails came off and when; an occupant raised over the stated raising period with no loosening and no recorded reason fails (C-7).
- **GR-12** Cradle cost is held under a stated fraction of the work's cost; where it is not, the work is recorded as kept manual or scripted, as an outcome, not a defect (C-8).

---

## 12. Use at each scale

The engine and its invariants do not change with scale. What changes is who authors content, how many cradles share it, and how records move.

**Personal.** One person wants an agent to sort, file and pay invoices. The engine runs on their machine; the seat is their folders, their bank's portal, office hours. They author content: one encounter kind per invoice, a spill rule (misfiled or wrongly paid), a severity function (money and time to put it right), newcomer guardrails (propose only), and paying as a reserved action. A script and they run the chore through the cradle for a few weeks; that is the baseline. The agent enters and proposes, and after varied clean weeks the person edits content to let it file for known senders. The bank changes its portal; a narrowing rule they wrote earlier takes paying back behind approval at once. If the agent's proposals cost more to correct than they save, they stay manual. The same engine with other content raises an agent to keep the rules ledger of a long tabletop campaign, with story taste reserved.

**Enterprise.** An organisation runs hundreds of recurring operational jobs. One engine deployment hosts many cradles; seats are environments and on-call hours. Content is layered: a shared catalogue of kinds and a severity scale for customer impact, authored centrally; per-team guardrails and similarity rules, authored by each team. Each new model version enters as a new occupant in shadow mode. An agent cleared to deploy service A in business hours is not cleared for service B or at 2 am during an incident, because the content says so, and a query shows why. When a regulator asks why an agent ran a migration, the answer is query 1 of Section 8. Kinds that never earn trust stay scripted or human and their cradles are retired.

**Federated.** Several organisations or many individuals run their own engines on the shared record format. An occupant's record moves between them as evidence; each receiving cradle's content decides what counts. Shared catalogues and guides become a commons with a curator, and can be gamed or poisoned by authors who publish favourable definitions; that is a matter for the commons' own authors and curators.

---

## 13. Engine questions: three answered, three open

Authoring questions (likeness, thresholds, severity scales, identity after change) have moved to the guide (Section 9), with the board's positions kept. Of the six questions about the engine itself, the originator answered three on 2026-10-01 in the engine's own terms (the engine is neutral; every judgement is a rule someone writes). Three remain open.

**E-Q1. Who loads the first rules. Answered.** Whoever sets the cradle up: the user, or an AI working from the user's plain-language description. That first load is the first entry in the record, under its author's name, the way a designer loads the first level into an engine. The engine needs no special authority for it: the record starts there, and every later transition can be traced back to it. E-7 is worded to match.

**E-Q2. Content an occupant writes about itself. Answered.** The engine refuses nothing on opinion. An occupant may write or change content about itself, through recorded transitions under its own name. Whether that content takes effect is decided by other content the user writes, for example: content an occupant writes about itself takes effect only after a person approves it. The engine's guarantee is E-1, E-3 and E-4: the record shows who wrote every rule, and nobody edits the record. This replaces the earlier convention that an occupant never authors content governing itself (C-6 and GR-08 are rewritten to match). The board's concern that the guardian never moves inside is now carried by the user's approval content, not by an engine refusal.

**E-Q3. Outside services. Answered.** Building the connection to an outside service (a bank portal, another team's service) is the occupant's work: it writes the module that connects the service and proves, through the cradle, that the integration works. The module's calls and the service's responses pass through the engine's doors, so they are recorded with their conditions like any transition; the rule for what counts as proven (for example, test payments that match the bank's statement) is content. The integration earns trust like any other task and goes back to proving itself when the service changes. What the engine witnesses is the calls and responses, not the outside service's internal state; the proving content is where that gap is closed.

**E-Q4. Occupant identity at the engine level. Open, narrowed.** The engine must attribute every transition to an actor. Whether two runs of the same model with different instructions are one actor or two is a content question for agency, but the engine still needs some identity to record. By the same logic as E-Q2, the engine records the name and observed makeup (model, instructions, tools) an actor acts under, and content decides whether two are the same occupant. Still open: how the engine confirms that an actor is who it says it is, which no content can supply.

**E-Q5. One engine for all procedural work. Open.** The correction settles the old product-versus-protocol question: the engine is the product, the record format is the protocol, the guide is the pattern. Still open is whether one engine can be general enough. The skeptic's point stands that game engines work because they fix physics, time and rendering, and are general only at the bottom and genre-specific a few layers up. Whether a neutral graph-and-transition engine is enough for all procedural work, or needs domain layers between engine and content, is unknown until a second, unlike domain is built on it.

**E-Q6. Cost of neutrality. Open.** Every rule as content, every act recorded, every agency rebuildable may cost more than the work in small cradles. ER-11 makes the cost visible; whether a minimal engine can stay under the skeptic's bound for one person's chores is untested.

---

## 14. Glossary

**Agency.** What an occupant may do here, now: content in force applied to the record. Never stored apart from them.

**Author.** Anyone who writes content: designer, parent, team, guardian. Acts through the same doors as any participant.

**Baby box.** The engine, the record format, a reference cradle with sample content, and the guide.

**Content.** Opinionated rules and readings, as data, versioned, with a named author, loaded by a recorded transition.

**Cradle.** The neutral engine: state graph, transitions, record, queries. With content loaded, the cradle for one kind of work.

**Door.** One way to change state through the engine; the only way.

**Encounter.** One meeting between occupant and work, defined by content over recorded transitions. Also called a rep.

**Guardian.** An author who reads an occupant's record and changes content to widen or narrow its freedom; outside the engine and the occupant.

**Guardrail.** One limit in content on what an occupant may do.

**Guide.** Advice to authors on what content to write, by how raising is going.

**Occupant.** The actor being raised.

**Race-car bed.** The cradle with content that has taken many guardrails off for proven situations; the full harness.

**Rep.** The originator's word for an encounter.

**Reserved action.** An action content declares does not loosen by record alone.

**Seat.** The station the engine runs on, observed with every transition.

**Severity.** A scalar from an authored function applied to a recorded change.

**Situation.** The observed conditions of a transition. The board's context.

**Spill.** An outcome that fell short, as classified by an authored rule applied to a recorded change.

**Transition.** One change to state through a door, recorded with actor, situation and content in force.

**Witnessing.** Establishing what happened without asking the occupant; the engine's job, by recording every transition.
