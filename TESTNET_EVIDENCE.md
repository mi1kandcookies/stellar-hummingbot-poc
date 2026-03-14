# Testnet Transaction Evidence

All transactions below were executed on the Stellar testnet and can be independently verified on [Stellar Expert](https://stellar.expert/explorer/testnet).

## Accounts

| Role | Public Key |
|------|-----------|
| Master (trader) | `GA74O7WJYPBOZOSDQR5UFN4Z3WF4LB3SBFXIQPQ6TDA3I6KFSAIFJVDV` |
| USDC Issuer | `GDI5CSSFIWA2AL62WA2J4E2VQBM7QSHQCNLOQYK6K5MVCYJMQIS6IKRW` |
| Taker (counterparty) | `GC65I6GL5KFNGH6IEPXLSPKYLCCSHJ42XLGGHYIKCVABEXTNPSZQ4QJH` |
| Channel 1 | `GA76IWJ4LQWTOVTWUEFLYONBY4WMKS65VI2YDCUQKVZGBIUVW6ZH2YGN` |
| Channel 2 | `GA7A6UK2QXULDJLPYF4MBGH2BHZ3D6PSKNGCBMLQGS5MYD36HIPYQTDE` |
| Channel 3 | `GD6D76X5M26FYZRGAEFVCKQ2CXOMHHZEOR3AWS2M3KF6GVDVL52AKTTT` |

## Transactions

| # | Operation | TX Hash | Explorer Link |
|---|-----------|---------|---------------|
| 1 | Friendbot funding (master) | `448bea874acce997c2721a4b6affd4a14bce1b088f9114b67e594ade66b54dcf` | [View](https://stellar.expert/explorer/testnet/tx/448bea874acce997c2721a4b6affd4a14bce1b088f9114b67e594ade66b54dcf) |
| 2 | Friendbot funding (USDC issuer) | `3a12d5e01ba57646d6c4788098804423d83470c33100f454a9a6b4b1fd97eebc` | [View](https://stellar.expert/explorer/testnet/tx/3a12d5e01ba57646d6c4788098804423d83470c33100f454a9a6b4b1fd97eebc) |
| 3 | USDC trustline on master (ChangeTrust) | `eeb614ac46c362ba4f19e7b2386b649c363cccf2b6699e2ca77c9618064c9322` | [View](https://stellar.expert/explorer/testnet/tx/eeb614ac46c362ba4f19e7b2386b649c363cccf2b6699e2ca77c9618064c9322) |
| 4 | Mint 1,000 USDC to master | `d8cfe4388e61fa24bb564ba7dddaf10a43a05d51dca534722955cefd41612832` | [View](https://stellar.expert/explorer/testnet/tx/d8cfe4388e61fa24bb564ba7dddaf10a43a05d51dca534722955cefd41612832) |
| 5 | Friendbot funding (taker) | `b52565952adebfd06bbaf85caf017f73fb1e89221ee7856c87a3a06117652728` | [View](https://stellar.expert/explorer/testnet/tx/b52565952adebfd06bbaf85caf017f73fb1e89221ee7856c87a3a06117652728) |
| 6 | USDC trustline on taker | `b6f9c171c2e9983e6bb2813f6738ad0e4ab28ed4c6bcf88d801ca2fa39cb1c9e` | [View](https://stellar.expert/explorer/testnet/tx/b6f9c171c2e9983e6bb2813f6738ad0e4ab28ed4c6bcf88d801ca2fa39cb1c9e) |
| 7 | Mint 500 USDC to taker | `bb2abc623b733223addcf6f881bd82cd3da83eb743787a6758d93fbc02dba77e` | [View](https://stellar.expert/explorer/testnet/tx/bb2abc623b733223addcf6f881bd82cd3da83eb743787a6758d93fbc02dba77e) |
| 8 | Batched channel creation (3 accounts) | `bd58b663a8d2952a22e59030657a61f71f4b9086e834fbdc15f9c8389c050afe` | [View](https://stellar.expert/explorer/testnet/tx/bd58b663a8d2952a22e59030657a61f71f4b9086e834fbdc15f9c8389c050afe) |
| 9 | ManageSellOffer (10 XLM @ 0.50 USDC) | `127b8c5d35cbfca2e0c4a992b10cf51de6a48f87135caefef84c67f8ddbe91f5` | [View](https://stellar.expert/explorer/testnet/tx/127b8c5d35cbfca2e0c4a992b10cf51de6a48f87135caefef84c67f8ddbe91f5) |
| 10 | ManageBuyOffer (5 XLM @ 0.30 USDC) | `90174e7aae2cf4c04a6bb102499f2b171e03d34cea61bba0ffb12f0e30d13f68` | [View](https://stellar.expert/explorer/testnet/tx/90174e7aae2cf4c04a6bb102499f2b171e03d34cea61bba0ffb12f0e30d13f68) |
| 11 | **Taker crosses sell offer (real trade)** | `4a2dba88282a6e11157bfe200f3cfa399ff87eae94d53a5c953c3b58e69d8992` | [View](https://stellar.expert/explorer/testnet/tx/4a2dba88282a6e11157bfe200f3cfa399ff87eae94d53a5c953c3b58e69d8992) |
| 12 | Cancel sell offer remainder (offer 66286) | `0fe4aa22c1dc5fd49af43844b5fffc24b66b81a1f3f6b6451d2abe78b600ccd5` | [View](https://stellar.expert/explorer/testnet/tx/0fe4aa22c1dc5fd49af43844b5fffc24b66b81a1f3f6b6451d2abe78b600ccd5) |
| 13 | Cancel buy offer (offer 66288) | `82d432c793d037f8742137b2495651d4f469fdb1ed604f54f4776d03c0150751` | [View](https://stellar.expert/explorer/testnet/tx/82d432c793d037f8742137b2495651d4f469fdb1ed604f54f4776d03c0150751) |

## What Each Transaction Demonstrates

- **TX 1-2**: Account creation and funding via Friendbot
- **TX 3-4**: Asset lifecycle - trustline setup followed by USDC issuance from a dedicated issuer account
- **TX 5-7**: Independent taker account setup - Friendbot funding, trustline, and USDC allocation from issuer
- **TX 8**: Batched channel creation - single transaction with 3 `CreateAccount` operations, each funded with 2.0 XLM. This is the batching pattern described in our architecture doc Section 5.
- **TX 9**: Sell offer via channel 1 - channel is the transaction source, master account is the operation source (note the two signers). Offer ID 66286 extracted from result XDR.
- **TX 10**: Buy offer via channel 2 - same source-separation pattern, different channel, demonstrating parallel submission capability. Offer ID 66288.
- **TX 11**: **Two-party SDEX trade** - an independent taker account crosses master's sell offer. Taker submits a ManageBuyOffer at 0.60 USDC/XLM which matches against master's sell at 0.50 USDC/XLM, executing at the maker's price. This is a real trade between two separate accounts on the SDEX.
- **TX 12**: Cancel sell offer remainder - `ManageSellOffer` with amount=0 targeting offer 66286. The taker filled 5 of 10 XLM; this cancels the remaining 5.
- **TX 13**: Cancel buy offer - `ManageSellOffer` with amount=0 targeting offer 66288. Full lifecycle cleanup.

## SDEX Offer IDs

| Offer ID | Type | Asset Pair | Status |
|----------|------|-----------|--------|
| 66286 | ManageSellOffer | XLM/USDC | Partially filled (TX 11), remainder cancelled (TX 12) |
| 66288 | ManageBuyOffer | XLM/USDC | Cancelled (TX 13) |

## Trade Details

| Field | Value |
|-------|-------|
| Maker | Master account (GA74O7WJ...) |
| Taker | Taker account (GC65I6GL...) |
| Pair | XLM/USDC |
| Side | Maker sold XLM, taker bought XLM |
| Amount | 5 XLM |
| Price | 0.50 USDC/XLM (maker's price) |
| USDC transferred | 2.50 USDC |
