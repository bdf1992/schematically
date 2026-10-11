# Local-core qualification

`test-budget.json` owns the published profiles and exact production scope. Run
`python scripts/qualify_local.py --profile routine --prepared <prepared.json> --out <new-directory>`
only after WS admits the preparation environment and the coordinator freezes the
source. Routine allows 250 collected cases and 180 seconds; regression allows
10,000 and 1,200 seconds. Both require 75 percent executable-line coverage across
the complete declared production files, including source never executed.

Preparation is separate, bounded work: install declared development dependencies,
instrument a separate test copy, generate its HTML, and build Rust unit/native
binaries with `-C instrument-coverage` using the matching compiler and LLVM tools.
Retain preparation commands, source/dependency identities, artifacts and elapsed
cost. The supervisor never installs or compiles. A prepared assertion alone does
not prove how a binary was built; independent review checks its preparation record.

The prepared JSON contains absolute `sourceRoot`, `testCopyRoot`, `python`, `node`,
`rustTestBinary`, `nativeBinary`, `llvmProfdata`, `llvmCov`, `jsInitial`, and
`browserExecutable` paths. It also contains `sourceIdentity`, keyed by every
relative production path in `sourceScope` with its SHA-256; a nonempty
`toolVersions` object; and `dependencyFiles`, an explicit array of absolute lock,
tool/dependency and preparation-record paths. No token or private environment
contents belong in this file. Optional `buildRevision` supplies `SOV_BUILD_REVISION`
for deterministic stamped build checks. The runner retains hashes and safe environment
settings, actual Python package versions, and executable version output.

The queue contains native persistence/browser MCP, headless store/surface, Python
build, native MCP, and Rust unit suites. Each driver must collect without executing
tests: `--collect` prints one JSON case-ID array, or a consistent
`{suite,cases,count}` envelope. IDs must be globally unique. Execution receives
`--coverage-dir <JS-snapshot-directory>`; the copy root comes from the driver's
location. `SOV_SOURCE_ROOT`, `SOV_NATIVE_BINARY`, `CHROMIUM_PATH`, `COVERAGE_FILE`,
and `LLVM_PROFILE_FILE` are supplied by the supervisor. Each successful scenario
prints exactly `CASE PASS <id>`. Failed/skipped, unexpected, duplicate or missing
IDs fail. Rust uses `--list`, then serial `--nocapture` execution; its standard
case lines and summary must match collection without ignored/filtered tests.

Full collection finishes before any suite executes. A case ceiling violation
refuses execution. The supervising Windows Job Object contains the complete worker
and its descendants; each stage also uses bounded process containment with its
remaining monotonic allowance minus a five-second cleanup reserve. Combined logs,
commands and actual elapsed time remain available on failure. The profile ceiling
includes collection, identity checks, execution, coverage processing and cleanup.

A completed assertion failure may allow independent suites to continue only when
the supervisor proves containment and the native receipt proves clean cleanup
within its own deadline. Failed, skipped, missing or inconsistent cases still
prevent an overall pass. Reports distinguish explicitly reported execution from
unreported cases; work before an aborted assertion is not inferred as a pass.

Native qualification uses a fresh WebView2 profile beneath its retained output,
shared only across that suite's close/reopen checks. The child environment sets
`WEBVIEW2_USER_DATA_FOLDER`, following the [upstream WebView2 test guidance](https://github.com/microsoft/playwright/blob/main/docs/src/webview2.md).
Native stdout/stderr are retained with bounded redaction, alongside readiness
phase counts and process state. Earlier runs used the default profile; their
evidence does not establish that the installed application's recovery state was
unaffected. Qualification never clears that profile.

JavaScript instrumentation maps every scoped file to original source hashes.
`scripts/js_coverage.mjs merge` retains zero counters for never-executed modules
and merges exported snapshots. Python's coverage API analyzes original `build.py`
using compiled executable lines, including unexecuted source; coverage exclusions
fail. The build driver runs original `build.py` under coverage in-process or in a
child `coverage run` sharing `COVERAGE_FILE`. Generated HTML may be rewritten;
the nine frozen production sources must remain identical. LLVM merges
raw profiles from native and unit binaries and exports all function/file maps.
`llvm_tools.normalize_export` preserves missed functions, normalizes executable
line sets, and rejects absent scoped maps or disagreement with LLVM summaries.
The native production binary's map establishes the Rust executable denominator.
Unit-binary hits augment those lines; additional test-only maps remain recorded
without entering production coverage. This avoids counting inline `cfg(test)`
modules as production code and requires no textual source exclusions.
Developer checks and test harnesses are identity inputs, not production denominator.

`coverage.json` includes all nine production files, source hashes, executable/hit
lines and aggregate coverage. `evidence.json` retains policy, environment, queue,
case outcomes, logs and input identities. `supervision.json` records the outer
deadline/containment result. A pass requires both evidence and supervision passes;
changed source, tools, fixtures, harnesses or prepared binaries invalidate it.

Regression additionally retains the complete `STATIC`, `BROWSER` and `TAIL` queues
from `scripts/qa.py`. Those legacy scripts lack reliable case collection and
coverage adapters. The regression profile therefore returns an explicit unmet
check without running the old unsupervised queue. No historical suite is silently
dropped or counted as an invented case. A routine pass cannot establish release
readiness: regression, ARCH and independent native qualification remain required.
