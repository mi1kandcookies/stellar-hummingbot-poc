"""
Order management for SDEX offers.

Handles placement of sell and buy offers, cancellation, and XDR result
parsing to extract real offer IDs from the network response.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from stellar_sdk import (
    Account,
    Asset,
    Keypair,
    Server,
    TransactionBuilder,
)
from stellar_sdk.operation import ManageBuyOffer, ManageSellOffer
from stellar_sdk import xdr as stellar_xdr

from .config import BASE_FEE, HORIZON_URL, NETWORK_PASSPHRASE
from .utils import decimal_to_stellar_amount, stellar_amount_to_decimal

logger = logging.getLogger(__name__)


def _parse_offer_id_from_result(result_xdr: str) -> Optional[int]:
    """Extract the offer ID from a ManageOffer transaction result XDR.

    The result XDR contains a TransactionResult whose inner results include
    a ManageOfferSuccessResult with the offer ID.

    Args:
        result_xdr: Base64-encoded transaction result XDR.

    Returns:
        The offer_id if found, or None.
    """
    try:
        tx_result = stellar_xdr.TransactionResult.from_xdr(result_xdr)
        # Navigate to the operation results
        # tx_result.result.results is an array of OperationResult
        op_results = tx_result.result.results

        for op_result in op_results:
            tr = op_result.tr
            if tr is None:
                continue

            # Check for ManageSellOffer result
            manage_sell = getattr(tr, "manage_sell_offer_result", None)
            manage_buy = getattr(tr, "manage_buy_offer_result", None)

            result_obj = manage_sell or manage_buy
            if result_obj is None:
                continue

            success = getattr(result_obj, "success", None)
            if success is None:
                continue

            offer = getattr(success, "offer", None)
            if offer is None:
                continue

            # The offer field is a ManageOfferSuccessResultOffer
            # which can be empty (MANAGE_OFFER_DELETED) or contain an OfferEntry
            offer_entry = getattr(offer, "offer", None)
            if offer_entry is not None:
                return offer_entry.offer_id.int64
            else:
                # Offer was immediately filled or deleted - check offers_claimed
                return None

    except Exception as exc:
        logger.warning("Could not parse offer ID from result XDR: %s", exc)
        return None


def _check_available_balance(server: Server, account_id: str, asset: Asset) -> Decimal:
    """Check the available (spendable) balance for an asset on an account.

    For native XLM, subtracts the base reserve and subentry reserves.

    Args:
        server: Horizon Server instance.
        account_id: Public key of the account.
        asset: The asset to check.

    Returns:
        Available Decimal balance.
    """
    try:
        acct_info = server.accounts().account_id(account_id).call()
    except Exception as exc:
        logger.warning("Could not load account %s: %s", account_id[:8], exc)
        return Decimal("0")

    if asset.is_native():
        native_balance = Decimal("0")
        for bal in acct_info["balances"]:
            if bal["asset_type"] == "native":
                native_balance = stellar_amount_to_decimal(bal["balance"])
                break

        # Minimum balance = (2 + num_subentries) * base_reserve
        # base_reserve is 0.5 XLM on current mainnet
        num_subentries = acct_info.get("subentry_count", 0)
        base_reserve = Decimal("0.5")
        reserved = (2 + num_subentries) * base_reserve
        available = native_balance - reserved
        return max(available, Decimal("0"))
    else:
        for bal in acct_info["balances"]:
            if (
                bal.get("asset_code") == asset.code
                and bal.get("asset_issuer") == asset.issuer
            ):
                return stellar_amount_to_decimal(bal["balance"])
        return Decimal("0")


class OrderManager:
    """Manages SDEX offer placement and cancellation.

    Uses channel accounts as transaction sources while the master account
    is the logical owner of all offers.
    """

    def __init__(self, master_keypair: Keypair, server: Server):
        self.master_keypair = master_keypair
        self.server = server

    def place_sell_offer(
        self,
        selling_asset: Asset,
        buying_asset: Asset,
        amount: Decimal,
        price: Decimal,
        channel_keypair: Keypair,
    ) -> Dict[str, Any]:
        """Place a new sell offer on the SDEX.

        Args:
            selling_asset: Asset being sold.
            buying_asset: Asset being bought.
            amount: Amount of selling_asset to sell.
            price: Price in terms of buying_asset per unit of selling_asset.
            channel_keypair: Channel account keypair for tx submission.

        Returns:
            Dict with provisional_id (tx_hash) and offer_id (from result XDR).
        """
        # Pre-check balance
        available = _check_available_balance(
            self.server, self.master_keypair.public_key, selling_asset
        )
        logger.info(
            "Available %s balance: %s (need %s)",
            selling_asset.code if not selling_asset.is_native() else "XLM",
            available,
            amount,
        )

        # Build transaction with channel as source, master as op source
        channel_account = self.server.load_account(channel_keypair.public_key)

        builder = TransactionBuilder(
            source_account=channel_account,
            network_passphrase=NETWORK_PASSPHRASE,
            base_fee=BASE_FEE,
        )
        builder.set_timeout(30)

        builder.append_operation(
            ManageSellOffer(
                selling=selling_asset,
                buying=buying_asset,
                amount=decimal_to_stellar_amount(amount),
                price=str(price),
                offer_id=0,  # 0 = new offer
                source=self.master_keypair.public_key,
            )
        )

        tx = builder.build()
        tx.sign(channel_keypair)   # channel signs as tx source
        tx.sign(self.master_keypair)  # master signs as op source

        logger.info(
            "Submitting sell offer: %s %s for %s at price %s",
            amount,
            selling_asset.code if not selling_asset.is_native() else "XLM",
            buying_asset.code if not buying_asset.is_native() else "XLM",
            price,
        )

        response = self.server.submit_transaction(tx)
        tx_hash = response["hash"]
        logger.info("Sell offer submitted. TX: %s", tx_hash)

        # Extract real offer ID from result XDR
        result_xdr = response.get("result_xdr", "")
        offer_id = _parse_offer_id_from_result(result_xdr) if result_xdr else None

        return {
            "provisional_id": tx_hash,
            "offer_id": offer_id,
            "type": "sell",
        }

    def place_buy_offer(
        self,
        selling_asset: Asset,
        buying_asset: Asset,
        amount: Decimal,
        price: Decimal,
        channel_keypair: Keypair,
    ) -> Dict[str, Any]:
        """Place a new buy offer on the SDEX.

        The amount here is in terms of the buying_asset.

        Args:
            selling_asset: Asset being sold (what you pay with).
            buying_asset: Asset being bought (what you want to receive).
            amount: Amount of buying_asset to buy.
            price: Price in terms of selling_asset per unit of buying_asset.
            channel_keypair: Channel account keypair for tx submission.

        Returns:
            Dict with provisional_id (tx_hash) and offer_id (from result XDR).
        """
        # Pre-check balance of the selling asset (what we pay with)
        available = _check_available_balance(
            self.server, self.master_keypair.public_key, selling_asset
        )
        cost = amount * price
        logger.info(
            "Available %s balance: %s (need ~%s to buy %s %s)",
            selling_asset.code if not selling_asset.is_native() else "XLM",
            available,
            cost,
            amount,
            buying_asset.code if not buying_asset.is_native() else "XLM",
        )

        channel_account = self.server.load_account(channel_keypair.public_key)

        builder = TransactionBuilder(
            source_account=channel_account,
            network_passphrase=NETWORK_PASSPHRASE,
            base_fee=BASE_FEE,
        )
        builder.set_timeout(30)

        builder.append_operation(
            ManageBuyOffer(
                selling=selling_asset,
                buying=buying_asset,
                amount=decimal_to_stellar_amount(amount),
                price=str(price),
                offer_id=0,
                source=self.master_keypair.public_key,
            )
        )

        tx = builder.build()
        tx.sign(channel_keypair)
        tx.sign(self.master_keypair)

        logger.info(
            "Submitting buy offer: buy %s %s with %s at price %s",
            amount,
            buying_asset.code if not buying_asset.is_native() else "XLM",
            selling_asset.code if not selling_asset.is_native() else "XLM",
            price,
        )

        response = self.server.submit_transaction(tx)
        tx_hash = response["hash"]
        logger.info("Buy offer submitted. TX: %s", tx_hash)

        result_xdr = response.get("result_xdr", "")
        offer_id = _parse_offer_id_from_result(result_xdr) if result_xdr else None

        return {
            "provisional_id": tx_hash,
            "offer_id": offer_id,
            "type": "buy",
        }

    def cancel_offer(
        self,
        offer_id: int,
        selling_asset: Asset,
        buying_asset: Asset,
        channel_keypair: Keypair,
    ) -> Dict[str, Any]:
        """Cancel an existing offer by setting its amount to zero.

        Args:
            offer_id: The on-ledger offer ID to cancel.
            selling_asset: The selling asset of the offer.
            buying_asset: The buying asset of the offer.
            channel_keypair: Channel account keypair for tx submission.

        Returns:
            Dict with tx_hash and status.
        """
        channel_account = self.server.load_account(channel_keypair.public_key)

        builder = TransactionBuilder(
            source_account=channel_account,
            network_passphrase=NETWORK_PASSPHRASE,
            base_fee=BASE_FEE,
        )
        builder.set_timeout(30)

        # Cancel = ManageSellOffer with amount 0 and the target offer_id
        builder.append_operation(
            ManageSellOffer(
                selling=selling_asset,
                buying=buying_asset,
                amount="0",
                price="1",  # price is required but irrelevant for cancellation
                offer_id=offer_id,
                source=self.master_keypair.public_key,
            )
        )

        tx = builder.build()
        tx.sign(channel_keypair)
        tx.sign(self.master_keypair)

        logger.info("Cancelling offer %d", offer_id)

        try:
            response = self.server.submit_transaction(tx)
            tx_hash = response["hash"]
            logger.info("Offer %d cancelled. TX: %s", offer_id, tx_hash)
            return {"tx_hash": tx_hash, "status": "cancelled", "offer_id": offer_id}
        except Exception as exc:
            error_str = str(exc)
            # Handle "offer not found" gracefully - it may have already been
            # filled or cancelled
            if "op_not_found" in error_str or "MANAGE_SELL_OFFER_NOT_FOUND" in error_str:
                logger.info(
                    "Offer %d not found (likely already filled or cancelled). "
                    "Treating as success.",
                    offer_id,
                )
                return {"tx_hash": None, "status": "not_found", "offer_id": offer_id}
            raise
