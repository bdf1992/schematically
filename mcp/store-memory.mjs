// An in-memory document store for a hosted entrypoint or a test: no file, nothing durable across
// a process restart, and a writes counter so a caller can tell the surface persisted a mutation
// without reading the text back. Imports nothing.
export function createMemoryStore(text=null){
  let current=text;
  const store={
    writes:0,
    read(){return current},
    write(next){current=next;store.writes+=1}
  };
  return store;
}
