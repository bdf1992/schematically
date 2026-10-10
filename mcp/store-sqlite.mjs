// A database document store over node:sqlite (Node 22.13 or later, no flag, nothing installed):
// every document, every revision of it and the profile that owns it live in one SQLite file.
// Tables: profiles, documents, and an append-only revisions table; PRAGMA user_version is the
// schema version (1). A write of more than one statement runs inside BEGIN IMMEDIATE and COMMIT.
//
// The revision kept here counts the texts written for an id in this database (1 is the first
// text). It is not the revision field inside the document. Every revision keeps the whole text
// and nothing here removes one. Imports only node:sqlite.
import {DatabaseSync} from 'node:sqlite';

const SCHEMA_VERSION=1;
const SCHEMA=`
CREATE TABLE profiles(id TEXT PRIMARY KEY, created TEXT NOT NULL);
CREATE TABLE documents(id TEXT PRIMARY KEY, profile TEXT NOT NULL REFERENCES profiles(id), source TEXT, revision INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE revisions(document TEXT NOT NULL REFERENCES documents(id), revision INTEGER NOT NULL, origin TEXT NOT NULL CHECK(origin IN ('import','write')), written TEXT NOT NULL, text TEXT NOT NULL, PRIMARY KEY(document, revision));
`;

const now=()=>new Date().toISOString();
const plain=row=>row?{...row}:null;

export function openDatabase(file,{profile}){
  const db=new DatabaseSync(file);
  try{
    db.exec('PRAGMA foreign_keys=ON');
    db.exec('PRAGMA busy_timeout=5000');
    const version=db.prepare('PRAGMA user_version').get().user_version;
    if(version>SCHEMA_VERSION)throw new Error(`database schema version ${version} is newer than this server reads (${SCHEMA_VERSION})`);
    if(version===0){
      db.exec('BEGIN IMMEDIATE');
      try{
        db.exec(SCHEMA);
        db.exec(`PRAGMA user_version=${SCHEMA_VERSION}`);
        db.exec('COMMIT');
      }catch(error){db.exec('ROLLBACK');throw error}
    }
    db.prepare('INSERT OR IGNORE INTO profiles(id,created) VALUES(?,?)').run(profile,now());
  }catch(error){
    try{db.close()}catch(_){}
    throw error;
  }
  const columns='id,profile,source,revision,created,updated';
  const q={
    profiles:db.prepare('SELECT p.id AS id, p.created AS created, (SELECT COUNT(*) FROM documents d WHERE d.profile=p.id) AS documents FROM profiles p ORDER BY p.id'),
    hasProfile:db.prepare('SELECT 1 AS found FROM profiles WHERE id=?'),
    get:db.prepare(`SELECT ${columns} FROM documents WHERE id=?`),
    listAll:db.prepare(`SELECT ${columns} FROM documents ORDER BY id`),
    listOf:db.prepare(`SELECT ${columns} FROM documents WHERE profile=? ORDER BY id`),
    insert:db.prepare('INSERT INTO documents(id,profile,source,revision,created,updated) VALUES(?,?,?,0,?,?)'),
    text:db.prepare('SELECT r.text AS text FROM revisions r JOIN documents d ON d.id=r.document AND d.revision=r.revision WHERE d.id=?'),
    addRevision:db.prepare('INSERT INTO revisions(document,revision,origin,written,text) VALUES(?,?,?,?,?)'),
    bump:db.prepare('UPDATE documents SET revision=?, updated=? WHERE id=?')
  };
  const api={
    profile,
    profiles(){return q.profiles.all().map(plain)},
    hasProfile(id){return q.hasProfile.get(id)!==undefined},
    get(id){return plain(q.get.get(id))},
    list(profileId){return (profileId===undefined?q.listAll.all():q.listOf.all(profileId)).map(plain)},
    create(id,source){
      const stamp=now();
      q.insert.run(id,profile,typeof source==='string'?source:null,stamp,stamp);
      return api.get(id);
    },
    text(id){const row=q.text.get(id);return row?row.text:null},
    append(id,text,origin){
      const current=api.get(id);
      if(!current)throw new Error(`no document ${id}`);
      if(current.revision>0&&api.text(id)===text)return current.revision;
      db.exec('BEGIN IMMEDIATE');
      try{
        const latest=q.get.get(id).revision;
        const next=latest+1,stamp=now();
        q.addRevision.run(id,next,origin,stamp,text);
        q.bump.run(next,stamp,id);
        db.exec('COMMIT');
        return next;
      }catch(error){db.exec('ROLLBACK');throw error}
    },
    store(id){
      return {
        read(){return api.text(id)},
        write(text){api.append(id,text,'write')}
      };
    },
    close(){db.close()}
  };
  return api;
}
