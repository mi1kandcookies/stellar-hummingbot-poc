#!/usr/bin/env python3
"""
Stellar SDEX Hummingbot Proof of Concept — Demo Script

Demonstrates core SDEX operations on the Stellar testnet:
1. Account funding via Friendbot
2. Test asset issuance (USDC on testnet)
3. Trustline establishment
4. Channel account creation (batched)
5. Orderbook reading
6. Sell offer placement with two-phase order ID
7. Buy offer placement
8. Fill detection streaming
9. Offer cancellation
10. Channel fee replenishment check
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
from stellar_sdk.operation import ChangeTrust, Payment

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
    separator("STELLAR SDEX PROOF OF CONCEPT — TESTNET DEMO")

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
        print("Continuing without USDC — sell offers will still work.")
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
    # Step 3: Create and fund 3 channel accounts (batched)
    # ------------------------------------------------------------------
    separator("STEP 3: Create channel accounts (batched in single tx)")

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
    # Step 4: Fetch and display XLM/USDC orderbook
    # ------------------------------------------------------------------
    separator("STEP 4: Fetch orderbook")

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
    # Step 5: Place a sell offer (sell XLM for USDC) using channel 1
    # ------------------------------------------------------------------
    separator("STEP 5: Place sell offer (XLM -> USDC)")

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
    # Step 6: Place a buy offer (buy XLM with USDC) using channel 2
    # ------------------------------------------------------------------
    separator("STEP 6: Place buy offer (USDC -> XLM)")

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
                price=Decimal("0.30"),  # 0.30 USDC per XLM — below our sell at 0.50
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
    # Step 7: Start fill detection stream (brief, with timeout)
    # ------------------------------------------------------------------
    separator("STEP 7: Fill detection stream (5-second sample)")

    fill_events = []

    def on_fill(events):
        fill_events.extend(events)
        for ev in events:
            print(f"  Fill detected: offer_id={ev['offer_id']}, "
                  f"type={ev['fill_type']}, amount={ev.get('fill_amount')}")

    detector = FillDetector()
    print(f"Streaming transactions for {master_kp.public_key[:12]}...")
    print("(Listening for 5 seconds — fills from other market participants may appear)\n")

    await detector.run_with_timeout(
        account_id=master_kp.public_key,
        callback=on_fill,
        timeout=5.0,
    )

    if not fill_events:
        print("No fills detected during the sample window (expected for off-market offers).")

    # ------------------------------------------------------------------
    # Step 8: Cancel one offer
    # ------------------------------------------------------------------
    separator("STEP 8: Cancel an offer")

    if sell_result and sell_result.get("offer_id"):
        try:
            ch3 = await channel_mgr.acquire_channel()
            cancel_result = order_mgr.cancel_offer(
                offer_id=sell_result["offer_id"],
                selling_asset=XLM,
                buying_asset=USDC,
                channel_keypair=ch3,
            )
            if cancel_result.get("tx_hash"):
                tx_hashes.append(cancel_result["tx_hash"])
            print(f"Cancel result:")
            print(f"  Status:   {cancel_result['status']}")
            print(f"  TX hash:  {cancel_result.get('tx_hash', 'N/A')}")
            print(f"  Offer ID: {cancel_result['offer_id']}")
            await channel_mgr.release_channel(ch3)
        except Exception as exc:
            print(f"Cancel failed: {exc}")
            try:
                await channel_mgr.release_channel(ch3)
            except Exception:
                pass
    else:
        print("No sell offer to cancel (offer may have been immediately filled or failed).")

    # ------------------------------------------------------------------
    # Step 9: Channel replenishment check
    # ------------------------------------------------------------------
    separator("STEP 9: Channel replenishment check")

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
    # Step 10: Summary
    # ------------------------------------------------------------------
    separator("SUMMARY")

    print(f"Master account: {master_kp.public_key}")
    print(f"Network:        Stellar Testnet")
    print(f"Horizon:        {HORIZON_URL}")
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
