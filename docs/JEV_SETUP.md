# Jev setup: inside `poradar` and as an MCP tool for Codex and Claude Code

Jev is TypeSafe's System One model: state plus typed questions in, typed answers with probabilities out,
in roughly 70 to 500 ms. It does not stream, it does not write prose, and it does not run locally (no
published weights as of September 2026). `poradar` therefore treats it as an optional, consented cloud
decider; the local path is Ollama.

## 1. Keys (never paste a key into chat; never commit one)

Set one in your shell profile. `TYPESAFE_API_KEY` wins if both are set.

```sh
export OPENROUTER_API_KEY=...   # https://openrouter.ai/keys  (routes to /api/alpha/decisions)
# or
export TYPESAFE_API_KEY=...     # https://console.typesafe.ai/ (routes to /v1/systemone)
```

Pricing seen in public listings: about $0.042 per million input tokens, zero for output, so a single
ten-question scan on a 1500-character excerpt costs well under a thousandth of a cent (estimate, not
measured).

## 2. Inside poradar

```sh
poradar doctor                # shows "cloud route (if --cloud)" without revealing the key
poradar dryrun --cloud        # one real call on a bundled fixture; writes nothing
poradar scan article.txt --cloud
```

Response fields, verified against docs.typesafe.ai: choice answers carry `choice`, `probabilities`,
`confidence`; score answers carry `score`, `legend`, `probabilities`, `confidence`; noul answers carry
only `noul` (near 0.5 means uncertain, not medium). TypeSafe's own guidance uses a 0.5 confidence floor
for "genuinely unsure" and 0.9 for high-stakes actions; this app accepts at 0.6 and holds 0.3 to 0.6.

What Jev receives per item: `{"title", "source_domain", "published", "excerpt"}`; nothing else. What
comes back is gated in code (`decisions/gate.py`): accept at confidence 0.6 or above, uncertain between
0.3 and 0.6 (half weight, flagged for review), reject below.

## 3. As an MCP tool for Codex and Claude Code (the attached audit framework)

The community adapter `evaluate` (github.com/itsmostafa/typesafe-mcp, MIT) was inspected in this repo's
session: the installer downloads a checksum-verified release binary to `~/.local/bin`, no sudo, no
telemetry, no postinstall. It registers one read-only tool, `evaluate`, with Claude Code (user scope),
Codex, and Claude Desktop, carrying `TYPESAFE_*` and `OPENROUTER_API_KEY` from your shell into each
client's MCP config. Be aware: that means the key is stored in those client config files. Keep them
out of synced folders and repos.

```sh
curl -fsSL https://raw.githubusercontent.com/itsmostafa/typesafe-mcp/main/install.sh | sh
OPENROUTER_API_KEY=$OPENROUTER_API_KEY evaluate setup mcp
codex mcp list
claude mcp list
```

If a client was missed, register by hand (shown before you run it):

```sh
claude mcp add --scope user evaluate -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY -- "$HOME/.local/bin/evaluate" mcp
codex mcp add evaluate --env OPENROUTER_API_KEY=$OPENROUTER_API_KEY -- "$HOME/.local/bin/evaluate" mcp
```

Then, in either agent, run a scan interactively with the same bank this app uses:

> Use `evaluate` with the questions from `src/poradar/questions.json` and this state:
> `{"title": ..., "source_domain": ..., "published": ..., "excerpt": ...}`. Report each answer with its
> probability, and say which answers are below 0.6 confidence.

`poradar questions show` prints the bank in exactly the shape `evaluate` expects.

## 4. Rollback

- Remove the app's cloud path: unset the key or stop passing `--cloud`. Nothing is cached remotely.
- Remove the MCP tool: `claude mcp remove evaluate`, `codex mcp remove evaluate`, delete
  `~/.local/bin/evaluate`.
