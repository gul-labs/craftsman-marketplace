# Privacy Policy

_Last updated: 2026-10-01_

This policy covers the `craftsman` and `taxcraft` plugins and this repository. It is written to be
checkable: every claim below is something you can verify by reading the source, which is plain
Markdown plus local Node and Python scripts.

## The short version

**Neither plugin collects anything.** There is no telemetry, no analytics, no account, no server, and
no network call made by either plugin while it works. Nothing about you, your code, your audit
findings, or your tax documents is transmitted to the maintainer.

## What the plugins are

`craftsman` is declarative Markdown (`SKILL.md` plus `references/*.md` files) and local Node scripts
used for invariant checks and maintainer-only vendoring. It has no runtime dependencies. It is
instructions your agent reads, not a service you connect to.

`taxcraft` is the same shape plus a set of local Python tools (form, K-1, and statement parsers; a
workspace doctor; a dependency preflight). They run on your machine against files you point them at.
The preflight only probes for installed tools (`pdftotext --version` and the like) and prints an
install command for you to run; it installs nothing and downloads nothing. The only binary files in
either plugin are `taxcraft`'s synthetic PDF test fixtures under `tools/form-parser/fixtures/`, every
one generated from the readable values in `golden.json` by `make_fixtures.py` in the same folder.

## What they do with your data

- **Read** files you point them at: the project under audit for `craftsman`; bank statements,
  tax forms, K-1s, and ledgers for `taxcraft`.
- **Write** results to your own disk: `craftsman` to a `.craftsman/` workspace inside the audited
  project, which it instructs you to `.gitignore`; `taxcraft` to the tax workspace you choose.
- **Transmit nothing.** Your project files, audit findings, and tax documents do not leave your
  machine by any action of either plugin.
- **Record no secret values.** `craftsman` findings about a credential cite the file, line, and
  variable name only, never the value, and the audit never opens `.env` files to confirm one.

All review guidance ships bundled in the repository, including the vendored UX guideline list, so
an audit needs no network access to run.

## Important: your agent session is separate

This is the part a shorter policy would leave out.

Both plugins run *inside* a coding agent you are already using, such as Claude Code, Codex, or Cursor.
**That agent sends your code to its own provider in the normal course of operating**, and it would
do so with or without these plugins installed. Neither plugin adds a destination, changes what your
agent sends, or transmits anything on its own — but it also cannot prevent what your agent already
does.

So "the plugin transmits nothing" is a claim about these plugins, not a claim that your code stays on
your machine. For that, the relevant policy is your agent provider's:

- [Anthropic Privacy Policy](https://www.anthropic.com/legal/privacy) (Claude Code)
- your provider's equivalent, for any other agent

For `taxcraft` this matters more than usual: tax documents carry Social Security numbers, EINs,
and account numbers. The plugin keeps that data in local files, but your agent will see whatever
you show it. Redact what you don't need before you paste or point it at a file.

## The one script that does use the network

`scripts/refresh-web-interface-guidelines.mjs` downloads a SHA-pinned public source so a maintainer
can review upstream changes before a release. It is run manually by a maintainer, never during an
audit, an install, or ordinary plugin use. It sends nothing; it only fetches.

## What this repository does not contain

No telemetry hooks, no background process, no service endpoint that receives your project data, and
no bundled credentials or API keys.

## Cookies and tracking

None. There is no website and no hosted service associated with either plugin.

## Changes

Material changes to this policy are recorded in [CHANGELOG.md](./CHANGELOG.md) and dated at the top
of this file.

## Questions

Open a [GitHub issue](https://github.com/gul-labs/craftsman-marketplace/issues) or start a
[Discussion](https://github.com/gul-labs/craftsman-marketplace/discussions). For anything you
believe is a security concern, follow [SECURITY.md](./SECURITY.md) and use a private advisory
rather than a public issue.
