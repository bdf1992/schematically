'use strict';
// A node preload (NODE_OPTIONS=--require <this file>): loads src/07-graph-core.js and replaces its
// createSimulation, runScenario, createSession and tools with those of src/07-state-surface.js, so
// a suite written against dev's simulator runs on the state-space engine unchanged.
// tests/sim_parity_qa.py runs dev's sim-facing suites under it.
const path=require('path');
const src=path.join(__dirname,'..','src');
require(path.join(src,'06-attachment-core.js'));
require(path.join(src,'05-data-core.js'));
const G=require(path.join(src,'07-graph-core.js'));
const Surface=require(path.join(src,'07-state-surface.js'));
for(const name of ['createSimulation','runScenario','createSession','tools'])G[name]=Surface[name];
