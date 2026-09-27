// Standalone GLSP 2.8.0 browser client for the projection spike. Bundles the
// real @eclipse-glsp/client DEFAULT_MODULES (rendering, selection, move,
// create-edge/-node, delete, undo/redo, markers) against server.mjs over the
// same JSON-RPC-2.0-over-WebSocket wire @eclipse-glsp/protocol's
// GLSPWebSocketProvider/BaseJsonrpcGLSPClient speak. The only diagram-specific
// addition is view-module.mjs, which maps the projection's own node:<symbolId>
// types onto GLSP's stock rectangular node view -- no boundary, lock or
// reachability rule is decided here or in view-module.mjs.
import 'reflect-metadata';
import {
    BaseJsonrpcGLSPClient,
    DiagramLoader,
    GLSPActionDispatcher,
    GLSPWebSocketProvider,
    UndoAction,
    RedoAction,
    RequestExportSvgAction,
    baseViewModule,
    standaloneExportModule,
    createDiagramOptionsModule,
    initializeDiagramContainer
} from '@eclipse-glsp/client';
import { Container } from 'inversify';
import { projectionViewModule } from './view-module.mjs';

const params = new URLSearchParams(window.location.search);
const host = params.get('host') || '127.0.0.1';
const port = params.get('port') || '8790';
const clientId = 'sprotty';
const diagramType = 'schematic-diagram';
const webSocketUrl = `ws://${host}:${port}`;

function createContainer(options) {
    const container = new Container();
    initializeDiagramContainer(container, createDiagramOptionsModule(options), baseViewModule, projectionViewModule, standaloneExportModule);
    return container;
}

let glspClient;
let container;

async function initialize(connectionProvider) {
    glspClient = new BaseJsonrpcGLSPClient({ id: clientId, connectionProvider });
    container = createContainer({ clientId, diagramType, glspClientProvider: async () => glspClient, sourceUri: 'examples/08-gated-service.sov' });
    const actionDispatcher = container.get(GLSPActionDispatcher);
    const diagramLoader = container.get(DiagramLoader);
    await diagramLoader.load({ requestModelOptions: {} });

    // Exposed for client_qa.py (Playwright): the spike drives real GLSP
    // actions through the real dispatcher rather than clicking a tool
    // palette, since the server implements no RequestContextActions palette
    // provider (out of scope for this spike -- see REPORT.md).
    window.__glsp = {
        container,
        actionDispatcher,
        dispatch: action => actionDispatcher.dispatch(action),
        undo: () => actionDispatcher.dispatch(UndoAction.create()),
        redo: () => actionDispatcher.dispatch(RedoAction.create()),
        exportSvg: () => actionDispatcher.dispatch(RequestExportSvgAction.create())
    };
    window.__glspReady = true;
}

const wsProvider = new GLSPWebSocketProvider(webSocketUrl);
wsProvider.listen({ onConnection: initialize, logger: console });
