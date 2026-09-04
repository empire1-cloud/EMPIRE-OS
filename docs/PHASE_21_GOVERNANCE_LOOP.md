# Phase 21 — Canonical Runtime Activation and Continuous Command Loop

Phase 21 turns Empire OS from an advisory scaffold into a governed execution spine.

## Canonical chain

`AUTHORIZE → APPROVE → EXECUTE → VERIFY → RECONCILE → RESOLVE → SEAL`

The public shorthand remains:

`AUTHORIZE → APPROVE → EXECUTE → RECONCILE → RESOLVE`

Verification and receipt sealing are mandatory gates, not optional reporting steps.

## Non-negotiable controls

- Founder has final authority for medium, high, and critical actions.
- Deterministic policy—not an LLM—decides identity scope, risk, and approval requirements.
- Unknown action types are denied until registered.
- Destructive actions such as receipt deletion, audit erasure, ledger rewriting, and system deletion are hard-blocked.
- Raw API keys, passwords, access tokens, and private keys are rejected at intake.
- Executors must be explicitly registered. There is no arbitrary shell endpoint.
- Execution output must carry a digest that the verifier independently recomputes.
- Financial evidence must reconcile before resolution.
- A receipt can only be sealed after successful verification, reconciliation, and resolution.
- Receipts form a SHA-256 hash chain. Editing any prior receipt breaks chain verification.
- Idempotency keys prevent the same governed request from creating duplicate execution receipts.

## API

Base path: `/v1/governance`

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Runtime and receipt-chain status |
| `POST` | `/requests` | Intake, identity, policy, and risk classification |
| `POST` | `/requests/run` | Run until sealed or until a human/block/failure boundary |
| `GET` | `/requests` | List governed requests |
| `GET` | `/requests/{id}` | Inspect one request and its state history |
| `POST` | `/requests/{id}/approve` | Record founder approval or rejection |
| `POST` | `/requests/{id}/continue` | Continue after approval |
| `POST` | `/requests/{id}/execute` | Execute through a registered adapter |
| `POST` | `/requests/{id}/verify` | Verify execution evidence |
| `POST` | `/requests/{id}/reconcile` | Reconcile operational or ledger evidence |
| `POST` | `/requests/{id}/resolve` | Close a verified and reconciled action |
| `POST` | `/requests/{id}/seal` | Append a tamper-evident receipt |
| `GET` | `/receipts` | List sealed receipts |
| `GET` | `/receipts/{id}` | Inspect one receipt |
| `GET` | `/receipts/verify-chain` | Verify the full receipt chain |

## Built-in proof action

`demo.echo` is the deliberately narrow proof executor. It proves that the complete governance loop works without pretending to perform repository, deployment, payment, or messaging actions.

Real capabilities are added through `GovernanceEngine.register_executor(action_type, adapter)` and remain subject to the same policy, approval, verification, reconciliation, and receipt gates.

## Example

```bash
curl -X POST http://localhost:8787/v1/governance/requests/run \
  -H 'content-type: application/json' \
  -d '{
    "action_type": "demo.echo",
    "actor": {
      "actor_id": "cofounder-agent-1",
      "role": "agent",
      "universe": "empire1",
      "scopes": ["demo.echo"]
    },
    "parameters": {"message": "No execution without verification"},
    "idempotency_key": "phase21-proof-1"
  }'
```

Expected terminal state: `sealed`.
