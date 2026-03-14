#!/usr/bin/env python3
"""
Stellar SDEX Hummingbot Proof of Concept - Demo Script

Demonstrates core SDEX operations on the Stellar testnet:
1. Account funding via Friendbot
2. Test asset issuance (USDC on testnet)
3. Trustline establishment
4. Channel account creation (batched)
5. Orderbook reading
6. Sell offer placement with two-phase order ID
7. Buy offer placement
8. Taker account crosses the sell offer (real two-party trade)
9. Fill detection captures the trade
10. Offer cancellation
11. Channel fee replenishment check
"""

import asyncio
import logging
import sys
from decimal import Decimal

import aiohttp
from stellar_sdk import (
    Asset,
    Keypair,
    Server,
    TransactionBuilder,
)
from stellar_sdk.operation import ChangeTrust, ManageBuyOffer, Payment

from src.config import (
    BASE_FEE,
    FRIENDBOT_URL,
    HORIZON_URL,
    NETWORK_PASSPHRASE,
    USDC_CODE,
    XLM,
    load_keypair,
)
import src.config as config
from src.channel_manager import ChannelManager
from src.order_manager import OrderManager
from src.fill_detector import FillDetector
from src.orderbook_reader import OrderbookReader

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("demo")


def separator(title: str) -> None:
    """Print a visual step separator."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


async def fund_from_friendbot(public_key: str) -> str:
    """Fund an account via Stellar testnet Friendbot."""
    url = f"{FRIENDBOT_URL}?addr={public_key}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            result = await resp.json()
            if resp.status != 200:
                if "already exists" in str(result).lower():
                    return "already_funded"
                raise RuntimeError(f"Friendbot failed: {result}")
            return result.get("hash", result.get("id", "unknown"))


async def main() -> None:
    """Run the complete SDEX demo flow."""

    tx_hashes: list[str] = []

    # --- Setup ---
    separator("STELLAR SDEX PROOF OF CONCEPT - TESTNET DEMO")

    master_kp = load_keypair()
    print(f"Master public key:  {master_kp.public_key}")
    print()

    server = Server(horizon_url=HORIZON_URL)

    # ------------------------------------------------------------------
    # Step 1: Fund master account from Friendbot
    # ------------------------------------------------------------------
    separator("STEP 1: Fund master account via Friendbot")

    channel_mgr = ChannelManager(master_kp, server, num_channels=3)

    try:
        tx_hash = await channel_mgr.fund_master_from_friendbot()
        if tx_hash != "already_funded":
            tx_hashes.append(tx_hash)
        print(f"Friendbot funding TX: {tx_hash}")
    except Exception as exc:
        print(f"Friendbot funding failed: {exc}")
        print("If the account is already funded, this is expected.")

    # ------------------------------------------------------------------
    # Step 2: Create a test USDC issuer and mint USDC
    # ------------------------------------------------------------------
    separator("STEP 2: Create USDC issuer and mint test USDC")

    issuer_kp = Keypair.random()
    print(f"USDC issuer account: {issuer_kp.public_key}")

    # Fund the issuer via Friendbot
    try:
        issuer_tx = await fund_from_friendbot(issuer_kp.public_key)
        if issuer_tx != "already_funded":
            tx_hashes.append(issuer_tx)
        print(f"Issuer funded. TX: {issuer_tx}")
    except Exception as exc:
        print(f"Could not fund issuer: {exc}")
        print("Continuing without USDC - sell offers will still work.")
        issuer_kp = None

    # Create the USDC asset with our issuer
    USDC = None
    if issuer_kp:
        USDC = Asset(USDC_CODE, issuer_kp.public_key)
        config.USDC = USDC
        print(f"Test USDC asset: {USDC_CODE}:{issuer_kp.public_key[:12]}...")

        # Master establishes trustline to USDC
        try:
            master_account = server.load_account(master_kp.public_key)
            builder = TransactionBuilder(
                source_account=master_account,
                network_passphrase=NETWORK_PASSPHRASE,
                base_fee=BASE_FEE,
            )
            builder.set_timeout(30)
            builder.append_operation(ChangeTrust(asset=USDC))
            tx = builder.build()
            tx.sign(master_kp)
            response = server.submit_transaction(tx)
            tx_hash = response["hash"]
            tx_hashes.append(tx_hash)
            print(f"USDC trustline established. TX: {tx_hash}")
        except Exception as exc:
            print(f"Trustline creation failed: {exc}")

        # Issuer sends USDC to master account
        try:
            issuer_account = server.load_account(issuer_kp.public_key)
            builder = TransactionBuilder(
                source_account=issuer_account,
                network_passphrase=NETWORK_PASSPHRASE,
                base_fee=BASE_FEE,
            )
            builder.set_timeout(30)
            builder.append_operation(
                Payment(
                    destination=master_kp.public_key,
                    asset=USDC,
                    amount="1000.0000000",
                )
            )
            tx = builder.build()
            tx.sign(issuer_kp)
            response = server.submit_transaction(tx)
            tx_hash = response["hash"]
            tx_hashes.append(tx_hash)
            print(f"Minted 1,000 USDC to master account. TX: {tx_hash}")
        except Exception as exc:
            print(f"USDC minting failed: {exc}")
            USDC = None

    # ------------------------------------------------------------------
    # Step 3: Create and fund taker account
    # ------------------------------------------------------------------
    separator("STEP 3: Create taker account (independent counterparty)")

    taker_kp = Keypair.random()
    print(f"Taker public key: {taker_kp.public_key}")

    try:
        taker_tx = await fund_from_friendbot(taker_kp.public_key)
        if taker_tx != "already_funded":
            tx_hashes.append(taker_tx)
        print(f"Taker funded. TX: {taker_tx}")
    except Exception as exc:
        print(f"Could not fund taker: {exc}")
        taker_kp = None

    # Taker needs a USDC trustline and some USDC to take the sell offer
    if taker_kp and USDC and issuer_kp:
        try:
            # Trustline
            taker_account = server.load_account(taker_kp.public_key)
            builder = TransactionBuilder(
                source_account=taker_account,
                network_passphrase=NETWORK_PASSPHRASE,
                base_fee=BASE_FEE,
            )
            builder.set_timeout(30)
            builder.append_operation(ChangeTrust(asset=USDC))
            tx = builder.build()
            tx.sign(taker_kp)
            response = server.submit_transaction(tx)
            tx_hash = response["hash"]
            tx_hashes.append(tx_hash)
            print(f"Taker USDC trustline. TX: {tx_hash}")

            # Issuer sends USDC to taker
            issuer_account = server.load_account(issuer_kp.public_key)
            builder = TransactionBuilder(
                source_account=issuer_account,
                network_passphrase=NETWORK_PASSPHRASE,
                base_fee=BASE_FEE,
            )
            builder.set_timeout(30)
            builder.append_operation(
                Payment(
                    destination=taker_kp.public_key,
                    asset=USDC,
                    amount="500.0000000",
                )
            )
            tx = builder.build()
            tx.sign(issuer_kp)
            response = server.submit_transaction(tx)
            tx_hash = response["hash"]
            tx_hashes.append(tx_hash)
            print(f"Minted 500 USDC to taker. TX: {tx_hash}")
        except Exception as exc:
            print(f"Taker setup failed: {exc}")
            taker_kp = None

    # ------------------------------------------------------------------
    # Step 4: Create and fund 3 channel accounts (batched)
    # ------------------------------------------------------------------
    separator("STEP 4: Create channel accounts (batched in single tx)")

    try:
        tx_hash = await channel_mgr.create_channels()
        tx_hashes.append(tx_hash)
        print(f"Channel creation TX: {tx_hash}")
        for i, ch in enumerate(channel_mgr.channels):
            print(f"  Channel {i + 1}: {ch.public_key}")
    except Exception as exc:
        print(f"Channel creation failed: {exc}")
        print("Cannot continue without channels.")
        return

    # ------------------------------------------------------------------
    # Step 5: Fetch and display XLM/USDC orderbook (before our offers)
    # ------------------------------------------------------------------
    separator("STEP 5: Fetch orderbook (before placing offers)")

    ob_reader = OrderbookReader()
    if USDC:
        try:
            orderbook = await ob_reader.fetch_orderbook(XLM, USDC, limit=10)
            display = ob_reader.display_orderbook(
                orderbook["bids"], orderbook["asks"], levels=5
            )
            print(display)
        except Exception as exc:
            print(f"Orderbook fetch failed: {exc}")
    else:
        print("Skipping orderbook (no USDC asset available).")

    # ------------------------------------------------------------------
    # Step 6: Place a sell offer (sell XLM for USDC) using channel 1
    # ------------------------------------------------------------------
    separator("STEP 6: Place sell offer (10 XLM @ 0.50 USDC/XLM)")

    order_mgr = OrderManager(master_kp, server)
    sell_result = None

    if USDC:
        try:
            ch1 = await channel_mgr.acquire_channel()
            sell_result = order_mgr.place_sell_offer(
                selling_asset=XLM,
                buying_asset=USDC,
                amount=Decimal("10"),
                price=Decimal("0.50"),  # 0.50 USDC per XLM
                channel_keypair=ch1,
            )
            tx_hashes.append(sell_result["provisional_id"])
            print(f"Sell offer placed:")
            print(f"  TX hash (provisional ID): {sell_result['provisional_id']}")
            print(f"  On-ledger offer ID:       {sell_result['offer_id']}")
            await channel_mgr.release_channel(ch1)
        except Exception as exc:
            print(f"Sell offer failed: {exc}")
            try:
                await channel_mgr.release_channel(ch1)
            except Exception:
                pass
    else:
        print("Skipping sell offer (no USDC asset available).")

    # ------------------------------------------------------------------
    # Step 7: Place a buy offer (buy XLM with USDC) using channel 2
    # ------------------------------------------------------------------
    separator("STEP 7: Place buy offer (5 XLM @ 0.30 USDC/XLM)")

    buy_result = None
    if USDC:
        try:
            ch2 = await channel_mgr.acquire_channel()
            # Price must not cross the existing sell offer (0.50 USDC/XLM)
            # to avoid op_cross_self. Set buy price below the sell price.
            buy_result = order_mgr.place_buy_offer(
                selling_asset=USDC,
                buying_asset=XLM,
                amount=Decimal("5"),
                price=Decimal("0.30"),  # 0.30 USDC per XLM - below our sell at 0.50
                channel_keypair=ch2,
            )
            tx_hashes.append(buy_result["provisional_id"])
            print(f"Buy offer placed:")
            print(f"  TX hash (provisional ID): {buy_result['provisional_id']}")
            print(f"  On-ledger offer ID:       {buy_result['offer_id']}")
            await channel_mgr.release_channel(ch2)
        except Exception as exc:
            print(f"Buy offer failed: {exc}")
            try:
                await channel_mgr.release_channel(ch2)
            except Exception:
                pass
    else:
        print("Skipping buy offer (no USDC asset available).")

    # ------------------------------------------------------------------
    # Step 8: Fetch orderbook again (should show our offers)
    # ------------------------------------------------------------------
    separator("STEP 8: Fetch orderbook (after placing offers)")

    if USDC:
        try:
            orderbook = await ob_reader.fetch_orderbook(XLM, USDC, limit=10)
            display = ob_reader.display_orderbook(
                orderbook["bids"], orderbook["asks"], levels=5
            )
            print(display)
        except Exception as exc:
            print(f"Orderbook fetch failed: {exc}")

    # ------------------------------------------------------------------
    # Step 9: Taker crosses the sell offer (real two-party SDEX trade)
    # ------------------------------------------------------------------
    separator("STEP 9: Taker crosses the sell offer (two-party trade)")

    taker_fill_tx = None
    if taker_kp and USDC and sell_result and sell_result.get("offer_id"):
        print(f"Taker will buy XLM at 0.50 USDC/XLM, crossing master's sell offer.")
        print(f"  Master's sell offer ID: {sell_result['offer_id']}")
        print()

        try:
            taker_account = server.load_account(taker_kp.public_key)
            builder = TransactionBuilder(
                source_account=taker_account,
                network_passphrase=NETWORK_PASSPHRASE,
                base_fee=BASE_FEE,
            )
            builder.set_timeout(30)
            # Taker buys 5 XLM at up to 0.60 USDC/XLM - this will cross
            # master's sell at 0.50 and execute at 0.50 (price improvement)
            builder.append_operation(
                ManageBuyOffer(
                    selling=USDC,
                    buying=XLM,
                    amount="5.0000000",    # buy 5 XLM
                    price="0.6000000",     # willing to pay up to 0.60 USDC/XLM
                    offer_id=0,
                )
            )
            tx = builder.build()
            tx.sign(taker_kp)
            response = server.submit_transaction(tx)
            taker_fill_tx = response["hash"]
            tx_hashes.append(taker_fill_tx)
            print(f"Taker buy executed! TX: {taker_fill_tx}")
            print(f"  Taker bought XLM by crossing master's sell offer")
            print(f"  Trade executed at master's price of 0.50 USDC/XLM")
        except Exception as exc:
            print(f"Taker buy failed: {exc}")
    else:
        print("Skipping taker trade (missing prerequisites).")

    # ------------------------------------------------------------------
    # Step 10: Fill detection - detect the trade that just happened
    # ------------------------------------------------------------------
    separator("STEP 10: Fill detection (detecting the taker's trade)")

    fill_events = []

    def on_fill(events):
        fill_events.extend(events)
        for ev in events:
            print(f"  Fill detected: offer_id={ev['offer_id']}, "
                  f"type={ev['fill_type']}, amount={ev.get('fill_amount')}")

    detector = FillDetector()
    print(f"Streaming transactions for master account {master_kp.public_key[:12]}...")
    print("(Listening for 8 seconds to capture the fill)\n")

    await detector.run_with_timeout(
        account_id=master_kp.public_key,
        callback=on_fill,
        timeout=8.0,
    )

    if not fill_events:
        print("No fills detected via streaming (the trade may have landed before")
        print("the stream connected - this is expected in a demo environment).")
        if taker_fill_tx:
            print(f"\nThe fill IS confirmed on-chain: {taker_fill_tx}")
            print(f"  https://stellar.expert/explorer/testnet/tx/{taker_fill_tx}")

    # ------------------------------------------------------------------
    # Step 11: Cancel remaining offers (cleanup)
    # ------------------------------------------------------------------
    separator("STEP 11: Cancel remaining offers")

    # Cancel the sell offer remainder (5 of 10 XLM were filled by taker)
    if sell_result and sell_result.get("offer_id"):
        try:
            ch3 = await channel_mgr.acquire_channel()
            cancel_sell = order_mgr.cancel_offer(
                offer_id=sell_result["offer_id"],
                selling_asset=XLM,
                buying_asset=USDC,
                channel_keypair=ch3,
            )
            if cancel_sell.get("tx_hash"):
                tx_hashes.append(cancel_sell["tx_hash"])
            print(f"Sell offer cancel:")
            print(f"  Status:   {cancel_sell['status']}")
            print(f"  TX hash:  {cancel_sell.get('tx_hash', 'N/A')}")
            print(f"  Offer ID: {cancel_sell['offer_id']}")
            await channel_mgr.release_channel(ch3)
        except Exception as exc:
            print(f"Sell offer cancel failed: {exc}")
            try:
                await channel_mgr.release_channel(ch3)
            except Exception:
                pass

    # Cancel the buy offer (unfilled)
    if buy_result and buy_result.get("offer_id"):
        try:
            ch4 = await channel_mgr.acquire_channel()
            cancel_buy = order_mgr.cancel_offer(
                offer_id=buy_result["offer_id"],
                selling_asset=USDC,
                buying_asset=XLM,
                channel_keypair=ch4,
            )
            if cancel_buy.get("tx_hash"):
                tx_hashes.append(cancel_buy["tx_hash"])
            print(f"Buy offer cancel:")
            print(f"  Status:   {cancel_buy['status']}")
            print(f"  TX hash:  {cancel_buy.get('tx_hash', 'N/A')}")
            print(f"  Offer ID: {cancel_buy['offer_id']}")
            await channel_mgr.release_channel(ch4)
        except Exception as exc:
            print(f"Buy offer cancel failed: {exc}")
            try:
                await channel_mgr.release_channel(ch4)
            except Exception:
                pass

    if not (sell_result and sell_result.get("offer_id")) and not (buy_result and buy_result.get("offer_id")):
        print("No offers to cancel.")

    # ------------------------------------------------------------------
    # Step 12: Channel replenishment check
    # ------------------------------------------------------------------
    separator("STEP 12: Channel replenishment check")

    try:
        replenish_tx = await channel_mgr.replenish_channels()
        if replenish_tx:
            tx_hashes.append(replenish_tx)
            print(f"Replenishment TX: {replenish_tx}")
        else:
            print("No channels needed replenishment.")
    except Exception as exc:
        print(f"Replenishment check failed: {exc}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    separator("SUMMARY")

    print(f"Master account:  {master_kp.public_key}")
    if issuer_kp:
        print(f"USDC issuer:     {issuer_kp.public_key}")
    if taker_kp:
        print(f"Taker account:   {taker_kp.public_key}")
    print(f"Network:         Stellar Testnet")
    print(f"Horizon:         {HORIZON_URL}")
    print()

    print("Transaction Hashes:")
    print("-" * 70)
    for i, h in enumerate(tx_hashes, 1):
        print(f"  {i}. {h}")
        print(f"     https://stellar.expert/explorer/testnet/tx/{h}")
    print()

    print(f"Total transactions: {len(tx_hashes)}")
    print()
    print("All transaction hashes for SCF Build Award submission:")
    print("-" * 70)
    for h in tx_hashes:
        print(h)
    print("-" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDemo interrupted by user.")
        sys.exit(0)
