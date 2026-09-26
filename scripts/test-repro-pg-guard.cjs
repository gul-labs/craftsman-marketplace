const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const path = require('node:path')

const proof = path.join(__dirname, 'repro-pg-commit-outcome.cjs')
for (const [url, expected] of [
  ['postgres://u@127.0.0.1:5432/postgres?host=example.com', 'without query parameters'],
  ['postgres://u@example.com:5432/postgres', 'Only a loopback'],
  ['postgres://u@localhost:5432/postgres', 'Only a loopback'],
]) {
  const run = spawnSync(process.execPath, [proof], {
    encoding: 'utf8',
    env: { ...process.env, CRAFT_DB_PROOF: '1', DATABASE_URL: url },
  })
  assert.equal(run.status, 1, `guard unexpectedly accepted ${url}`)
  assert.match(run.stderr, new RegExp(expected))
}
console.log('PASS: proof harness rejects URL host overrides and non-loopback targets')
