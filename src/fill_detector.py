"""
Real-time fill detection via Horizon SSE transaction streaming.

Monitors an account's transactions via Server-Sent Events (SSE) and parses
the XDR transaction metadata to detect offer fills, partial fills, and
cancellations.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

import aiohttp
from stellar_sdk import xdr as stellar_xdr

from .config import HORIZON_URL
from .utils import from_stroops

logger = logging.getLogger(__name__)


def _extract_offer_changes_from_meta(meta_xdr: str) -> List[Dict[str, Any]]:
    """Parse TransactionMeta XDR to extract offer-related ledger changes.

    Handles meta versions 0, 1, 2, and 3 (v3 includes soroban data but the
    structure for classic operations is the same).

    Args:
        meta_xdr: Base64-encoded transaction meta XDR string.

    Returns:
        List of dicts describing offer changes, each with:
        - change_type: 'created', 'updated', or 'removed'
        - offer_id: int
        - For created/updated: seller_id, selling_asset, buying_asset,
          amount (Decimal), price_n, price_d
    """
    changes = []

    try:
        meta = stellar_xdr.TransactionMeta.from_xdr(meta_xdr)
    except Exception as exc:
        logger.warning("Failed to parse TransactionMeta XDR: %s", exc)
        return changes

    # Collect all LedgerEntryChanges from the appropriate meta version
    all_change_groups: list = []

    if meta.v == 0:
        # v0: array of OperationMeta, each with an array of LedgerEntryChanges
        if meta.operations is not None:
            for op_meta in meta.operations:
                if op_meta.changes is not None:
                    all_change_groups.append(op_meta.changes.ledger_entry_changes)
    elif meta.v == 1:
        # v1: tx_changes + operations
        if meta.v1 is not None:
            if meta.v1.tx_changes is not None:
                all_change_groups.append(meta.v1.tx_changes.ledger_entry_changes)
            if meta.v1.operations is not None:
                for op_meta in meta.v1.operations:
                    if op_meta.changes is not None:
                        all_change_groups.append(op_meta.changes.ledger_entry_changes)
    elif meta.v == 2:
        # v2: tx_changes_before, operations, tx_changes_after
        if meta.v2 is not None:
            if meta.v2.tx_changes_before is not None:
                all_change_groups.append(meta.v2.tx_changes_before.ledger_entry_changes)
            if meta.v2.operations is not None:
                for op_meta in meta.v2.operations:
                    if op_meta.changes is not None:
                        all_change_groups.append(op_meta.changes.ledger_entry_changes)
            if meta.v2.tx_changes_after is not None:
                all_change_groups.append(meta.v2.tx_changes_after.ledger_entry_changes)
    elif meta.v == 3:
        # v3: same structure as v2 with additional soroban fields (Protocol 20+)
        if meta.v3 is not None:
            if meta.v3.tx_changes_before is not None:
                all_change_groups.append(meta.v3.tx_changes_before.ledger_entry_changes)
            if meta.v3.operations is not None:
                for op_meta in meta.v3.operations:
                    if op_meta.changes is not None:
                        all_change_groups.append(op_meta.changes.ledger_entry_changes)
            if meta.v3.tx_changes_after is not None:
                all_change_groups.append(meta.v3.tx_changes_after.ledger_entry_changes)
    else:
        # v4 (Protocol 23) uses the same classic operation structure as v3.
        # The stellar-sdk may expose it as v3 with additional fields, or as
        # a distinct version. Attempt the v3-compatible path as a fallback.
        v3_compat = getattr(meta, "v3", None)
        if v3_compat is not None:
            if v3_compat.tx_changes_before is not None:
                all_change_groups.append(v3_compat.tx_changes_before.ledger_entry_changes)
            if v3_compat.operations is not None:
                for op_meta in v3_compat.operations:
                    if op_meta.changes is not None:
                        all_change_groups.append(op_meta.changes.ledger_entry_changes)
            if v3_compat.tx_changes_after is not None:
                all_change_groups.append(v3_compat.tx_changes_after.ledger_entry_changes)
        else:
            logger.warning("Unhandled TransactionMeta version: %d", meta.v)

    # Process each LedgerEntryChange
    for change_group in all_change_groups:
        for change in change_group:
            change_dict = _process_ledger_entry_change(change)
            if change_dict is not None:
                changes.append(change_dict)

    return changes


def _process_ledger_entry_change(
    change: stellar_xdr.LedgerEntryChange,
) -> Optional[Dict[str, Any]]:
    """Process a single LedgerEntryChange and extract offer data if present.

    Args:
        change: A single LedgerEntryChange XDR object.

    Returns:
        Dict with offer change info, or None if not offer-related.
    """
    change_type = change.type

    if change_type == stellar_xdr.LedgerEntryChangeType.LEDGER_ENTRY_CREATED:
        entry = change.created
        if entry is not None and entry.data.type == stellar_xdr.LedgerEntryType.OFFER:
            offer = entry.data.offer
            return _offer_entry_to_dict(offer, "created")

    elif change_type == stellar_xdr.LedgerEntryChangeType.LEDGER_ENTRY_UPDATED:
        entry = change.updated
        if entry is not None and entry.data.type == stellar_xdr.LedgerEntryType.OFFER:
            offer = entry.data.offer
            return _offer_entry_to_dict(offer, "updated")

    elif change_type == stellar_xdr.LedgerEntryChangeType.LEDGER_ENTRY_REMOVED:
        key = change.removed
        if key is not None and key.type == stellar_xdr.LedgerEntryType.OFFER:
            return {
                "change_type": "removed",
                "offer_id": key.offer.offer_id.int64,
            }

    elif change_type == stellar_xdr.LedgerEntryChangeType.LEDGER_ENTRY_STATE:
        # State entries are the "before" snapshot - useful for computing deltas
        entry = change.state
        if entry is not None and entry.data.type == stellar_xdr.LedgerEntryType.OFFER:
            offer = entry.data.offer
            return _offer_entry_to_dict(offer, "state")

    return None


def _offer_entry_to_dict(offer: stellar_xdr.OfferEntry, change_type: str) -> Dict[str, Any]:
    """Convert an OfferEntry XDR object to a readable dict.

    Args:
        offer: OfferEntry XDR object.
        change_type: One of 'created', 'updated', 'state'.

    Returns:
        Dict with offer details.
    """
    return {
        "change_type": change_type,
        "offer_id": offer.offer_id.int64,
        "seller_id": offer.seller_id.account_id.ed25519.uint256.hex(),
        "amount": from_stroops(offer.amount.int64),
        "price_n": offer.price.n.int32,
        "price_d": offer.price.d.int32,
    }


def compute_fill_from_changes(changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compute fill amounts from a sequence of offer changes.

    For each offer_id, looks for state -> updated/removed transitions:
    - state -> updated: partial fill, amount = state.amount - updated.amount
    - state -> removed: full fill (or cancellation)
    - created: new offer placed

    Args:
        changes: List of offer change dicts from _extract_offer_changes_from_meta.

    Returns:
        List of fill event dicts.
    """
    fills = []
    # Group by offer_id, tracking state entries
    state_by_offer: Dict[int, Dict] = {}

    for change in changes:
        offer_id = change["offer_id"]

        if change["change_type"] == "state":
            state_by_offer[offer_id] = change

        elif change["change_type"] == "updated":
            prev = state_by_offer.get(offer_id)
            if prev is not None:
                fill_amount = prev["amount"] - change["amount"]
                if fill_amount > Decimal("0"):
                    fills.append({
                        "offer_id": offer_id,
                        "fill_type": "partial",
                        "fill_amount": fill_amount,
                        "remaining_amount": change["amount"],
                    })

        elif change["change_type"] == "removed":
            prev = state_by_offer.get(offer_id)
            if prev is not None:
                fills.append({
                    "offer_id": offer_id,
                    "fill_type": "full_or_cancelled",
                    "fill_amount": prev["amount"],
                    "remaining_amount": Decimal("0"),
                })
            else:
                fills.append({
                    "offer_id": offer_id,
                    "fill_type": "removed",
                    "fill_amount": None,
                    "remaining_amount": Decimal("0"),
                })

        elif change["change_type"] == "created":
            fills.append({
                "offer_id": offer_id,
                "fill_type": "new_offer",
                "fill_amount": Decimal("0"),
                "remaining_amount": change["amount"],
            })

    return fills


class FillDetector:
    """Streams account transactions and detects offer fills in real time.

    Uses Horizon's SSE (Server-Sent Events) endpoint to receive new
    transactions as they are confirmed on the ledger.
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start_stream(
        self,
        account_id: str,
        callback: Callable[[List[Dict[str, Any]]], None],
        timeout: float = 10.0,
    ) -> None:
        """Start streaming transactions for an account and invoke callback on fills.

        Args:
            account_id: Public key of the account to monitor.
            callback: Function called with a list of fill events for each tx.
            timeout: Maximum seconds to stream before stopping.
        """
        # Manual SSE parsing instead of stellar-sdk streaming for full control
        # over cursor management, reconnection logic, and async cancellation.
        self._running = True
        url = f"{HORIZON_URL}/accounts/{account_id}/transactions"
        params = {"cursor": "now", "order": "asc"}
        headers = {"Accept": "text/event-stream"}

        logger.info("Starting fill detection stream for %s (timeout=%ss)", account_id[:8], timeout)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    if resp.status != 200:
                        logger.error("SSE stream returned status %d", resp.status)
                        return

                    buffer = ""
                    async for chunk in resp.content:
                        if not self._running:
                            break

                        buffer += chunk.decode("utf-8", errors="replace")

                        # SSE events are separated by double newlines
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            self._process_sse_event(event_str, callback)

        except asyncio.TimeoutError:
            logger.info("Fill detection stream timed out after %ss (expected)", timeout)
        except asyncio.CancelledError:
            logger.info("Fill detection stream cancelled")
        except Exception as exc:
            logger.warning("Fill detection stream error: %s", exc)
        finally:
            self._running = False
            logger.info("Fill detection stream stopped")

    def _process_sse_event(
        self,
        event_str: str,
        callback: Callable[[List[Dict[str, Any]]], None],
    ) -> None:
        """Parse an SSE event string and extract fills if it's a transaction.

        Args:
            event_str: Raw SSE event text.
            callback: Fill callback function.
        """
        import json

        data_lines = []
        for line in event_str.strip().split("\n"):
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())

        if not data_lines:
            return

        data_str = "\n".join(data_lines)
        if data_str == '"hello"' or not data_str.startswith("{"):
            return

        try:
            tx_data = json.loads(data_str)
        except json.JSONDecodeError:
            return

        result_meta_xdr = tx_data.get("result_meta_xdr")
        if not result_meta_xdr:
            return

        tx_hash = tx_data.get("hash", "unknown")
        changes = _extract_offer_changes_from_meta(result_meta_xdr)

        if changes:
            fills = compute_fill_from_changes(changes)
            if fills:
                logger.info("Detected %d fill event(s) in TX %s", len(fills), tx_hash[:12])
                callback(fills)

    def stop_stream(self) -> None:
        """Signal the stream to stop."""
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            logger.info("Fill detection stream stop requested")

    async def run_with_timeout(
        self,
        account_id: str,
        callback: Callable[[List[Dict[str, Any]]], None],
        timeout: float = 10.0,
    ) -> None:
        """Convenience wrapper: run the stream with a timeout.

        Args:
            account_id: Public key to monitor.
            callback: Fill event callback.
            timeout: Seconds before auto-stop.
        """
        self._task = asyncio.create_task(
            self.start_stream(account_id, callback, timeout=timeout)
        )
        try:
            await self._task
        except asyncio.CancelledError:
            pass
