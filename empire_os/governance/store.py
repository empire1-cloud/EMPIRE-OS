from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import ActionRecord, ChainVerification, SealedReceipt, model_to_dict, utc_now


def canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def digest(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def validate_model(model_cls, payload):
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(payload)
    return model_cls.parse_obj(payload)


class GovernanceStore:
    """Thread-safe JSON persistence with an in-memory mode for tests/serverless demos."""

    def __init__(self, path: str | Path | None = None, persist: bool = True):
        configured = path or os.getenv("EMPIRE_GOVERNANCE_STORE", "./data/governance.json")
        self.path = Path(configured)
        self.persist = persist
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {"records": {}, "receipts": [], "idempotency": {}}
        self._load()

    def _load(self) -> None:
        if not self.persist or not self.path.exists():
            return
        with self._lock:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("Governance store root must be a JSON object.")
            self._data.update(loaded)

    def _save(self) -> None:
        if not self.persist:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True, default=str), encoding="utf-8")
        os.replace(tmp, self.path)

    def find_by_idempotency_key(self, key: str) -> Optional[ActionRecord]:
        with self._lock:
            request_id = self._data["idempotency"].get(key)
            return self.get_record(request_id) if request_id else None

    def save_record(self, record: ActionRecord) -> ActionRecord:
        with self._lock:
            record.updated_at = utc_now()
            payload = model_to_dict(record)
            self._data["records"][record.request_id] = payload
            if record.request.idempotency_key:
                self._data["idempotency"][record.request.idempotency_key] = record.request_id
            self._save()
            return record

    def get_record(self, request_id: str) -> Optional[ActionRecord]:
        with self._lock:
            payload = self._data["records"].get(request_id)
            return validate_model(ActionRecord, payload) if payload else None

    def list_records(self) -> List[ActionRecord]:
        with self._lock:
            return [validate_model(ActionRecord, item) for item in self._data["records"].values()]

    def seal(self, record: ActionRecord) -> SealedReceipt:
        with self._lock:
            receipts = self._data["receipts"]
            previous_hash = receipts[-1]["receipt_hash"] if receipts else "GENESIS"
            payload = model_to_dict(record)
            sequence = len(receipts) + 1
            sealed_at = utc_now()
            hash_input = {
                "sequence": sequence,
                "request_id": record.request_id,
                "previous_hash": previous_hash,
                "payload": payload,
                "sealed_at": sealed_at.isoformat(),
            }
            receipt_hash = digest(hash_input)
            receipt = SealedReceipt(
                sequence=sequence,
                request_id=record.request_id,
                previous_hash=previous_hash,
                payload=payload,
                receipt_hash=receipt_hash,
                sealed_at=sealed_at,
            )
            receipts.append(model_to_dict(receipt))
            self._save()
            return receipt

    def get_receipt(self, receipt_id: str) -> Optional[SealedReceipt]:
        with self._lock:
            for payload in self._data["receipts"]:
                if payload["receipt_id"] == receipt_id:
                    return validate_model(SealedReceipt, payload)
        return None

    def list_receipts(self) -> List[SealedReceipt]:
        with self._lock:
            return [validate_model(SealedReceipt, item) for item in self._data["receipts"]]

    def verify_chain(self) -> ChainVerification:
        with self._lock:
            previous_hash = "GENESIS"
            receipts = self._data["receipts"]
            for expected_sequence, payload in enumerate(receipts, start=1):
                receipt = validate_model(SealedReceipt, payload)
                if receipt.sequence != expected_sequence:
                    return ChainVerification(
                        valid=False,
                        receipt_count=len(receipts),
                        broken_at_sequence=expected_sequence,
                        reason="Receipt sequence is not contiguous.",
                    )
                if receipt.previous_hash != previous_hash:
                    return ChainVerification(
                        valid=False,
                        receipt_count=len(receipts),
                        broken_at_sequence=expected_sequence,
                        reason="Previous receipt hash does not match.",
                    )
                hash_input = {
                    "sequence": receipt.sequence,
                    "request_id": receipt.request_id,
                    "previous_hash": receipt.previous_hash,
                    "payload": receipt.payload,
                    "sealed_at": receipt.sealed_at.isoformat(),
                }
                expected_hash = digest(hash_input)
                if receipt.receipt_hash != expected_hash:
                    return ChainVerification(
                        valid=False,
                        receipt_count=len(receipts),
                        broken_at_sequence=expected_sequence,
                        reason="Receipt payload hash mismatch.",
                    )
                previous_hash = receipt.receipt_hash

            return ChainVerification(valid=True, receipt_count=len(receipts))
