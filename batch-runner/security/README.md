# Agentic Live Authorization

No live Agentic Sandbox key or approval is checked in during non-paid
implementation. Before an approved live phase, the owner must add the reviewed
Ed25519 public key at `agentic-owner-ed25519.pub`; the private key must remain
outside this repository and outside every compute runner.

The dedicated live control workflow must provide runtime-only
`AGENTIC_SIGNED_APPROVAL_PATH` and `AGENTIC_NONCE_LEDGER_PATH` values. The
general batch workflow rejects agentic treatment and hardened baseline modes
before any cloud or Hugging Face credential step.