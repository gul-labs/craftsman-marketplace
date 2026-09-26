// Dated evidence harness, not application code. See docs/postgres-commit-proof-2026-09-25.md.
const assert = require('node:assert/strict')
const { createRequire } = require('node:module')
const path = require('node:path')
const { readFileSync } = require('node:fs')

if (process.env.CRAFT_DB_PROOF !== '1') {
  throw new Error('Set CRAFT_DB_PROOF=1 to run this destructive proof on a throwaway database')
}
const connectionString = process.env.DATABASE_URL
if (!connectionString) throw new Error('DATABASE_URL is required')
const parsed = new URL(connectionString)
if (!['postgres:', 'postgresql:'].includes(parsed.protocol) || parsed.search || parsed.hash) {
  throw new Error('Use a PostgreSQL URL without query parameters or fragments')
}
const isLoopback = host => ['127.0.0.1', '::1'].includes(host.replace(/^\[(.*)\]$/, '$1'))
if (!isLoopback(parsed.hostname)) {
  throw new Error('Only a loopback Postgres URL is allowed')
}
const moduleRoot = process.env.CRAFT_DB_MODULE_ROOT
if (!moduleRoot || !path.isAbsolute(moduleRoot)) {
  throw new Error('CRAFT_DB_MODULE_ROOT must be the absolute path of a package with pg and drizzle-orm installed')
}
const load = createRequire(path.join(moduleRoot, 'package.json'))
const { Pool, Client } = load('pg')
const effectiveHost = new Client({ connectionString }).connectionParameters.host
if (!isLoopback(effectiveHost)) {
  throw new Error('The driver resolved a non-loopback host')
}
const { drizzle } = load('drizzle-orm/node-postgres')
const { sql } = load('drizzle-orm')
const versions = {
  node: process.version,
  pg: load('pg/package.json').version,
  drizzle: JSON.parse(readFileSync(path.join(moduleRoot, 'node_modules/drizzle-orm/package.json'), 'utf8')).version,
}
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
const proofSchema = `craft_pg_proof_${process.pid}_${Date.now()}`

class Deadline extends Error {}
class UnknownCommit extends Error {}

// The minimal phase/deadline behavior under review. This is not a production helper.
async function transaction(pool, fn, deadlineMs) {
  const deadlineAt = Date.now() + deadlineMs
  let phase = 'acquiring'
  let client
  let acquisition
  let timer
  let failed = false
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(phase === 'commit-possible' ? new UnknownCommit() : new Deadline()), deadlineMs)
  })
  try {
    acquisition = pool.connect()
    client = await Promise.race([acquisition, timeout])
    if (Date.now() >= deadlineAt) throw new Deadline()
    phase = 'running'
    const work = drizzle(client).transaction(async tx => {
      const value = await fn(tx)
      if (Date.now() >= deadlineAt) throw new Deadline()
      phase = 'commit-possible'
      return value
    })
    return await Promise.race([work, timeout])
  } catch (error) {
    failed = true
    if (phase === 'commit-possible' && !(error instanceof UnknownCommit)) {
      throw new UnknownCommit('COMMIT result unconfirmed', { cause: error })
    }
    throw error
  } finally {
    clearTimeout(timer)
    if (client) client.release(failed ? true : undefined)
    else if (acquisition) void acquisition.then(late => late.release(true), () => {})
  }
}

async function main() {
  const admin = new Client({ connectionString })
  await admin.connect()
  try {
    const server = await admin.query('SHOW server_version')
    console.log(JSON.stringify({ versions, postgres: server.rows[0].server_version }))
    await admin.query(`CREATE SCHEMA "${proofSchema}"`)
    await admin.query(`CREATE TABLE "${proofSchema}".proof (id int primary key)`)
    await admin.query(`CREATE FUNCTION "${proofSchema}".slow_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(0.3); RETURN NULL; END $$`)
    await admin.query(`CREATE CONSTRAINT TRIGGER slow_commit_trigger AFTER INSERT ON "${proofSchema}".proof DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION "${proofSchema}".slow_commit()`)

    const pool = new Pool({ connectionString, max: 1, connectionTimeoutMillis: 1000, query_timeout: 100 })
    pool.on('error', () => {})
    pool.on('connect', client => client.on('error', () => {}))
    try {
      const blocker = await pool.connect()
      const started = Date.now()
      await assert.rejects(transaction(pool, async () => {}, 80), error => error instanceof Deadline)
      const elapsed = Date.now() - started
      assert(elapsed < 250, `acquisition deadline took ${elapsed}ms`)
      blocker.release()
      await delay(120)
      assert.equal(pool.totalCount, 0, 'late acquired client should be destroyed')
      console.log(`acquisition deadline: ${elapsed}ms; late client destroyed`)

      let unknown
      try {
        await transaction(pool, async tx => {
          await tx.execute(sql.raw(`INSERT INTO "${proofSchema}".proof (id) VALUES (1)`))
        }, 2000)
      } catch (error) {
        unknown = error
      }
      assert(unknown instanceof UnknownCommit, `expected unknown COMMIT; got ${unknown}`)
      await delay(400)
      const rows = await admin.query(`SELECT count(*)::int AS n FROM "${proofSchema}".proof WHERE id = 1`)
      assert.equal(rows.rows[0].n, 1, 'COMMIT should have persisted despite local timeout')
      console.log(`local COMMIT timeout: ${unknown.cause?.message}; persisted=1; outcome classified unknown`)
    } finally {
      await pool.end()
    }
  } finally {
    await admin.query(`DROP SCHEMA IF EXISTS "${proofSchema}" CASCADE`)
    await admin.end()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
