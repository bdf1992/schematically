// Test-only graceful stop so NODE_V8_COVERAGE is written before the supervisor closes the process tree.
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  if (chunk.split(/\r?\n/).includes('SOV_TEST_STOP')) process.exit(0);
});
