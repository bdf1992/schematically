# Source of the Work Engine map

`gapmap.json` is an unchanged copy of
`C:\Users\bdf19\workstation\control\sketchbooks\ep-CatalystCoreV2-sandbox-8d673072\gapmap.json`,
copied on 2026-10-01 with `python docs/workengine/build_map.py --refresh-source`. The sketchbook
it came from is collected when its case ends, so this copy is the map's source from now on.

Its own `meta.read_on` is 2026-09-27: the date the gap map was written from the Work Engine
package and a read of `wskernel`. `meta.package` and `meta.kernel_checked` name what it was read
from; `meta.status_rule` says what exists, partial and missing mean.

`docs/workengine/build_map.py` turns it into `docs/workengine/map.sov`;
`docs/workengine/check_map.py` checks that every record, surface and query appears once with its
status.
