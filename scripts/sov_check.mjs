// The one headless check of a .sov payload, shared by scripts/validate_sov.mjs and
// bin/schematically.mjs. It runs the data core's validateDocument and then the refusal the
// browser makes at load time when a bound wire has no shared surface (carrierCanvasId), so a file
// that passes here also opens in the editor.
//
//   checkText(Data, text) -> {doc, diagnostics}
//
// Each diagnostic is {code, subject, message}: `code` is stable, `subject` the record it is about
// ('document', or the id the message opens with), `message` the core's own words.

export function checkText(Data, text) {
  let doc;
  try {
    doc = Data.documentFromFilePayload(JSON.parse(text));
  } catch (error) {
    return {doc: null, diagnostics: [{code: 'DOCUMENT_UNREADABLE', subject: 'document', message: error.message}]};
  }
  const diagnostics = Data.validateDocument(doc).errors.map(message => ({code: 'DOCUMENT_INVALID', subject: subjectOf(message), message}));
  for (const wire of doc.wires) {
    let surface;
    try { surface = Data.carrierCanvasId(doc, wire, wire.canvasId || null); }
    catch (error) {
      if (!diagnostics.some(d => d.message.startsWith(`wire ${wire.id}`))) {
        diagnostics.push({code: 'WIRE_NO_SHARED_SURFACE', subject: wire.id, message: `wire ${wire.id}: ${error.message}`});
      }
      continue;
    }
    // The loader derives a missing wire.canvasId from the ends; one that is written but names a
    // different surface is kept as written and routes there, so report the disagreement.
    const stored = wire.canvasId || null;
    if (surface !== Data.GLOBAL_CANVAS_ID && stored !== surface) {
      diagnostics.push({code: 'WIRE_CANVAS_MISMATCH', subject: wire.id,
        message: `wire ${wire.id}: canvasId ${stored ? `is ${stored}` : 'missing'}; both ends are on ${surface}, set "canvasId": "${surface}"`});
    }
  }
  return {doc, diagnostics};
}

function subjectOf(message) {
  const m = /^(?:wire|component|record|port)\s+([^\s:]+)/i.exec(message);
  return m ? m[1] : 'document';
}
