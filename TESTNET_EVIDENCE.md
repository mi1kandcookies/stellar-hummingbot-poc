# Testnet Transaction Evidence

All transactions below were executed on the Stellar testnet and can be independently verified on [Stellar Expert](https://stellar.expert/explorer/testnet).

## Accounts

| Role | Public Key |
|------|-----------|
| Master (trader) | `GDEJ4N67LUACGB24TUQHCVNIHBEB7WBJAIF5E5KEUSARB33UVHCBHHJB` |
| USDC Issuer | `GCBVXE5QXMSHJS3ZMLBAFRBMAJNSEZFLQORMNZJLWLE5S5KU3PFVTVNU` |
| Taker (counterparty) | `GADKFWQFYKGPCDWIHMWQR7YOMDY73G5SC5QXOPRVBQ7MSPR24S44JGSD` |
| Channel 1 | `GADAG4MYKFEG7BNRHJERBM7AM6Z7NH6WMZUD4HLQAWU2VCVQLUD2JPIJ` |
| Channel 2 | `GAKGML3MCZYQ3LHUNQT5EF55VCM2XNWY3B4K6XAFBYW7TSKA44R7FENX` |
| Channel 3 | `GBOHA5QSMHGRYGD6STUJTFS3N7UIVCO3UA4D5XNJ3Q6RWTHC25CFDGQW` |

## Transactions

| # | Operation | TX Hash | Explorer Link |
|---|-----------|---------|---------------|
| 1 | Friendbot funding (master) | `c688cc8ad187614f0770a16e34f65955fa149127d2eb11e5e8e161171f2111a8` | [View](https://stellar.expert/explorer/testnet/tx/c688cc8ad187614f0770a16e34f65955fa149127d2eb11e5e8e161171f2111a8) |
| 2 | Friendbot funding (USDC issuer) | `dc44c31e3c8a1b49820f9c6df5bb14f8b6509f3fb35479594b138a2191700df0` | [View](https://stellar.expert/explorer/testnet/tx/dc44c31e3c8a1b49820f9c6df5bb14f8b6509f3fb35479594b138a2191700df0) |
| 3 | USDC trustline on master (ChangeTrust) | `4565b86fdaeef3ae470a389d206e734bfea37fbe24fd9518cfb3a11fed3645ce` | [View](https://stellar.expert/explorer/testnet/tx/4565b86fdaeef3ae470a389d206e734bfea37fbe24fd9518cfb3a11fed3645ce) |
| 4 | Mint 1,000 USDC to master | `d8e28dc344e68611d0808f536ccb82ec8a5dcf32282c0b0e9e351ebcea6e90cd` | [View](https://stellar.expert/explorer/testnet/tx/d8e28dc344e68611d0808f536ccb82ec8a5dcf32282c0b0e9e351ebcea6e90cd) |
| 5 | Friendbot funding (taker) | `a01274c32dc1c26f0b84b26e6935468e933eb26ff3e161f91bdf9225943d9512` | [View](https://stellar.expert/explorer/testnet/tx/a01274c32dc1c26f0b84b26e6935468e933eb26ff3e161f91bdf9225943d9512) |
| 6 | USDC trustline on taker | `ff512477c85c0c8931bdeda9476dd87afa275b2fe7ef8424ce8249247f75e366` | [View](https://stellar.expert/explorer/testnet/tx/ff512477c85c0c8931bdeda9476dd87afa275b2fe7ef8424ce8249247f75e366) |
| 7 | Mint 500 USDC to taker | `62515efa8c3b35c536013de3d89225aae08a4170a032550028abf161c00c36b1` | [View](https://stellar.expert/explorer/testnet/tx/62515efa8c3b35c536013de3d89225aae08a4170a032550028abf161c00c36b1) |
| 8 | Batched channel creation (3 accounts) | `ccd99350cebbce67344a2e6d2349499b2e150b1fb7bc3b58f90b18b7f06c11b3` | [View](https://stellar.expert/explorer/testnet/tx/ccd99350cebbce67344a2e6d2349499b2e150b1fb7bc3b58f90b18b7f06c11b3) |
| 9 | ManageSellOffer (10 XLM @ 0.50 USDC) | `6bb5aeba28489ee85bf556a53608069e4e6b5ef757329d5d842baf90033c5e65` | [View](https://stellar.expert/explorer/testnet/tx/6bb5aeba28489ee85bf556a53608069e4e6b5ef757329d5d842baf90033c5e65) |
| 10 | ManageBuyOffer (5 XLM @ 0.30 USDC) | `a94a991846000c07a2105642bfb643efecb2b809d84b1fe6b8bff864eeb39e85` | [View](https://stellar.expert/explorer/testnet/tx/a94a991846000c07a2105642bfb643efecb2b809d84b1fe6b8bff864eeb39e85) |
| 11 | **Taker crosses sell offer (real trade)** | `0c41fae936a81fe38c3c9420c96028e65ec31e4a38d92dac0494d2e679da0887` | [View](https://stellar.expert/explorer/testnet/tx/0c41fae936a81fe38c3c9420c96028e65ec31e4a38d92dac0494d2e679da0887) |
| 12 | Cancel buy offer (offer 66282) | `8f86edbb93b215b4c8e3e8752a243a780bce51df3d26222e90062885d99ce3dd` | [View](https://stellar.expert/explorer/testnet/tx/8f86edbb93b215b4c8e3e8752a243a780bce51df3d26222e90062885d99ce3dd) |

## What Each Transaction Demonstrates

- **TX 1-2**: Account creation and funding via Friendbot
- **TX 3-4**: Asset lifecycle — trustline setup followed by USDC issuance from a dedicated issuer account
- **TX 5-7**: Independent taker account setup — Friendbot funding, trustline, and USDC allocation from issuer
- **TX 8**: Batched channel creation — single transaction with 3 `CreateAccount` operations, each funded with 2.0 XLM. This is the batching pattern described in our architecture doc Section 5.
- **TX 9**: Sell offer via channel 1 — channel is the transaction source, master account is the operation source (note the two signers). Offer ID 66281 extracted from result XDR.
- **TX 10**: Buy offer via channel 2 — same source-separation pattern, different channel, demonstrating parallel submission capability. Offer ID 66282.
- **TX 11**: **Two-party SDEX trade** — an independent taker account crosses master's sell offer. Taker submits a ManageBuyOffer at 0.60 USDC/XLM which matches against master's sell at 0.50 USDC/XLM, executing at the maker's price. This is a real trade between two separate accounts on the SDEX.
- **TX 12**: Offer cancellation — `ManageSellOffer` with amount=0 targeting offer 66282. Demonstrates graceful lifecycle management.

## SDEX Offer IDs

| Offer ID | Type | Asset Pair | Status |
|----------|------|-----------|--------|
| 66281 | ManageSellOffer | XLM/USDC | Filled (TX 11 — taker crossed) |
| 66282 | ManageBuyOffer | XLM/USDC | Cancelled (TX 12) |

## Trade Details

| Field | Value |
|-------|-------|
| Maker | Master account (GDEJ4N67...) |
| Taker | Taker account (GADKFWQF...) |
| Pair | XLM/USDC |
| Side | Maker sold XLM, taker bought XLM |
| Amount | 5 XLM |
| Price | 0.50 USDC/XLM (maker's price) |
| USDC transferred | 2.50 USDC |
