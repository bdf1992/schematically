// Registers the projection's own GModel types (node:<symbolId> for each
// component symbol in examples/08-gated-service.sov) onto GLSP's stock
// rectangular node view. 'graph', 'edge' and 'port' already resolve through
// @eclipse-glsp/client's baseViewModule (adapter.mjs's types match
// DefaultTypes.GRAPH/EDGE/PORT verbatim) -- this module adds nothing for
// those, and decides no legality of its own, same as adapter.mjs/server.mjs.
import { FeatureModule, GNode, RectangularNodeView, configureModelElement } from '@eclipse-glsp/client';

const SYMBOL_IDS = ['authority', 'act', 'plane', 'gate', 'hold', 'receipt'];

export const projectionViewModule = new FeatureModule(
    (bind, unbind, isBound, rebind) => {
        const context = { bind, unbind, isBound, rebind };
        for (const symbolId of SYMBOL_IDS) {
            configureModelElement(context, `node:${symbolId}`, GNode, RectangularNodeView);
        }
    },
    { featureId: Symbol('projectionView') }
);
