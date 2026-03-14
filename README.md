# Stellar SDEX Hummingbot Proof of Concept

A standalone Python proof-of-concept demonstrating core Stellar SDEX (Stellar Decentralized Exchange) operations on testnet. Built as part of the Stellar Hummingbot SDEX Connector proposal for the SCF Build Award.

## What This Demonstrates

- **Channel Account Management**: Creating and managing a pool of channel accounts for concurrent transaction submission, with automatic balance replenishment.
- **SDEX Order Placement**: Placing sell offers (`ManageSellOffer`) and buy offers (`ManageBuyOffer`) through channel accounts, with two-phase order ID tracking (provisional tx hash to on-ledger offer ID).
- **Offer Cancellation**: Cancelling existing offers with graceful handling of already-filled/cancelled offers.
- **Fill Detection**: Real-time streaming of account transactions via Horizon SSE, with XDR parsing of `TransactionMeta` (v0/v1/v2/v3) to detect offer fills and compute fill amounts from ledger entry changes.
- **Orderbook Reading**: Fetching and displaying SDEX orderbook snapshots with spread calculation.
- **Stellar Internals**: Proper handling of sequence numbers, base reserves, stroop conversion, trustlines, and XDR result parsing.

## Prerequisites

- Python 3.10+
- `stellar-sdk` >= 10.0.0
- `aiohttp`

## Installation

```bash
# Clone the repo
cd stellar-hummingbot-poc

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Demo

```bash
# Run with a new random keypair (default)
python demo.py

# Or set a specific secret key
export STELLAR_SECRET_KEY=SXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
python demo.py
```

The demo will:
1. Generate or load a master keypair
2. Fund it via Stellar testnet Friendbot
3. Establish a USDC trustline
4. Create 3 channel accounts in a single batched transaction
5. Fetch and display the XLM/USDC orderbook
6. Place a sell offer and a buy offer through separate channels
7. Run a 5-second fill detection stream
8. Cancel an outstanding offer
9. Check channel balances and replenish if needed
10. Print a summary with all transaction hashes

## Architecture

```
demo.py                     Main demo orchestrator
src/
  config.py                 Network config, keypair loading, asset definitions
  channel_manager.py        Channel account pool with async acquire/release
  order_manager.py          Offer placement, cancellation, XDR result parsing
  fill_detector.py          SSE streaming, TransactionMeta XDR parsing
  orderbook_reader.py       Horizon /order_book REST API reader
  utils.py                  Stroop conversion, asset encoding, Decimal helpers
```

**Key design decisions:**
- Channel accounts use the master account as the operation source (`source` field on each operation), allowing the master to own all offers and trustlines while channels handle sequence numbers independently.
- Fill detection parses raw XDR `TransactionMeta` rather than relying on Horizon effects, giving access to exact pre/post offer amounts for precise fill calculation.
- Offers use a two-phase ID system: the transaction hash serves as a provisional ID for immediate tracking, then the real on-ledger offer ID is extracted from the result XDR.

## Transaction Hashes

Transaction hashes will be populated after running on testnet. Each hash links to the Stellar Expert testnet explorer for verification.

## License

MIT
