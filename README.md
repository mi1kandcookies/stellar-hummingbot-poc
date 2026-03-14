# Stellar SDEX Hummingbot Proof of Concept

A standalone Python proof-of-concept demonstrating core Stellar SDEX operations on testnet. Built as part of the Stellar Hummingbot SDEX Connector proposal for the SCF Build Award.

## What This Demonstrates

- **Channel Account Management** - Creating and managing a pool of channel accounts for concurrent transaction submission, with automatic balance replenishment
- **SDEX Order Placement** - Placing sell offers (ManageSellOffer) and buy offers (ManageBuyOffer) through channel accounts, with two-phase order ID tracking (provisional tx hash to on-ledger offer ID)
- **Two-Party SDEX Trade** - An independent taker account crosses the master's sell offer, producing a real trade between two separate accounts on the SDEX
- **Offer Cancellation** - Cancelling existing offers with graceful handling of already-filled/cancelled offers
- **Fill Detection** - Real-time streaming of account transactions via Horizon SSE, with XDR parsing of TransactionMeta (v0-v3) to detect offer fills and compute fill amounts from ledger entry changes
- **Orderbook Reading** - Fetching and displaying SDEX orderbook snapshots with spread calculation
- **Asset Issuance** - Creating a test USDC issuer, establishing trustlines, and minting tokens across accounts
- **Stellar Internals** - Sequence numbers, base reserves, stroop conversion, trustlines, and XDR result parsing

## Prerequisites

- Python 3.10+
- stellar-sdk >= 10.0.0
- aiohttp

## Installation

```bash
git clone https://github.com/mi1kandcookies/stellar-hummingbot-poc.git
cd stellar-hummingbot-poc

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

## Running the Demo

```bash
# Run with a new random keypair (default)
python demo.py

# Or set a specific secret key to reuse an account
export STELLAR_SECRET_KEY=SXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
python demo.py
```

No browser setup, wallets, or manual account creation required. The demo funds all accounts automatically via Stellar's testnet Friendbot.

## Demo Flow

1. Generate or load a master keypair
2. Fund master account via Friendbot
3. Create a USDC issuer account, establish trustlines, mint test USDC to master
4. Create an independent taker account with its own USDC balance
5. Create 3 channel accounts in a single batched transaction (2.0 XLM each)
6. Fetch and display the XLM/USDC orderbook (before and after placing offers)
7. Place a sell offer (10 XLM @ 0.50 USDC) via channel 1
8. Place a buy offer (5 XLM @ 0.30 USDC) via channel 2
9. Taker crosses the sell offer - real two-party SDEX trade at maker's price
10. Run fill detection stream (8 seconds)
11. Cancel both remaining offers (sell remainder + buy)
12. Check channel balances and replenish if needed
13. Print summary with all transaction hashes and Stellar Expert links

## Architecture

```
demo.py                     Main demo orchestrator (12 steps)
src/
  config.py                 Network config, keypair loading, asset definitions
  channel_manager.py        Channel account pool with async acquire/release
  order_manager.py          Offer placement, cancellation, XDR result parsing
  fill_detector.py          SSE streaming, TransactionMeta XDR parsing (v0-v3)
  orderbook_reader.py       Horizon /order_book REST API reader
  utils.py                  Stroop conversion, asset encoding, Decimal helpers
```

### Key Design Decisions

- **Channel source separation** - Channel accounts are the transaction source (pay the fee, own the sequence number). The master account is the operation source (owns all offers and trustlines). This allows parallel submission without sequence conflicts.
- **XDR-level fill detection** - Parses raw TransactionMeta XDR rather than relying on Horizon effects. This gives access to exact pre/post offer amounts for precise fill calculation, and correctly distinguishes LedgerEntry (CREATED/UPDATED) from LedgerKey (REMOVED).
- **Two-phase order ID** - The transaction hash serves as a provisional ID for immediate tracking, then the real on-ledger offer ID is extracted from the result XDR after confirmation.
- **Dynamic asset issuance** - USDC is created on-the-fly with a dedicated issuer account rather than depending on a hardcoded testnet issuer, demonstrating the full asset lifecycle.

## Transaction Evidence

The most recent run produced 13 on-chain testnet transactions across three independent accounts (master, taker, issuer). Full details with account IDs, offer IDs, and explorer links are in [TESTNET_EVIDENCE.md](TESTNET_EVIDENCE.md).

Key transactions:

| # | Operation | Explorer |
|---|-----------|----------|
| 8 | Batched channel creation (3 accounts) | [View](https://stellar.expert/explorer/testnet/tx/bd58b663a8d2952a22e59030657a61f71f4b9086e834fbdc15f9c8389c050afe) |
| 9 | ManageSellOffer via channel 1 | [View](https://stellar.expert/explorer/testnet/tx/127b8c5d35cbfca2e0c4a992b10cf51de6a48f87135caefef84c67f8ddbe91f5) |
| 10 | ManageBuyOffer via channel 2 | [View](https://stellar.expert/explorer/testnet/tx/90174e7aae2cf4c04a6bb102499f2b171e03d34cea61bba0ffb12f0e30d13f68) |
| 11 | **Taker crosses sell offer (real trade)** | [View](https://stellar.expert/explorer/testnet/tx/4a2dba88282a6e11157bfe200f3cfa399ff87eae94d53a5c953c3b58e69d8992) |
| 12 | Cancel sell offer remainder | [View](https://stellar.expert/explorer/testnet/tx/0fe4aa22c1dc5fd49af43844b5fffc24b66b81a1f3f6b6451d2abe78b600ccd5) |
| 13 | Cancel buy offer | [View](https://stellar.expert/explorer/testnet/tx/82d432c793d037f8742137b2495651d4f469fdb1ed604f54f4776d03c0150751) |

## Technical Documentation

- [Consolidated Technical Architecture](https://mi1kandcookies.github.io/stellar-hummingbot-poc/consolidated.html) - Key diagrams and decisions (10 sections)
- [Full Technical Architecture](https://mi1kandcookies.github.io/stellar-hummingbot-poc/) - Complete 14-section reference

## License

MIT
