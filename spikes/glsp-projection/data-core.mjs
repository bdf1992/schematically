// Loads the repository's own data core the same way mcp/server.mjs does:
// by file:// URL, so the spike never forks or reimplements it.
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '../..');

await import(pathToFileURL(path.join(REPO_ROOT, 'src/06-attachment-core.js')).href);
await import(pathToFileURL(path.join(REPO_ROOT, 'src/05-data-core.js')).href);

const Data = globalThis.SovSchematicData;
if (!Data) throw new Error('SovSchematicData core failed to load');

export default Data;
export { REPO_ROOT };
