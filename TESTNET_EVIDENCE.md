# Testnet Transaction Evidence

All transactions below were executed on the Stellar testnet and can be independently verified on [Stellar Expert](https://stellar.expert/explorer/testnet).

## Accounts

| Role | Public Key |
|------|-----------|
| Master (trader) | `GAWAGYP22DAN7LVUKJPKF2MLIY7Q2FKVBXS5DLRXRSHTLCHLRYXZBJBZ` |
| USDC Issuer | `GCE2IK5NTNIV3IIFR7EZLOR2QKRZK2FQWESFCRXLDRXIFOAI6CSNFYXK` |
| Channel 1 | `GAF4C4HF2S46VEV4B7CHTM2CAQTBANEMJFK477MGWSN6HJ6S2VVC7Z3A` |
| Channel 2 | `GCWXL6LQQY4PLEHIQPXP62D57BQJQH37RYJ5Z4FKPIWUF2CVZTEJSPCY` |
| Channel 3 | `GAPXS65I6V2LKWUP4BG6Z2CYE6BV2WRJUQNFNFGUXBIXUQLFQXSIALWD` |

## Transactions

| # | Operation | TX Hash | Explorer Link |
|---|-----------|---------|---------------|
| 1 | Friendbot funding (master) | `38cefe28249dc4584e16ad0a99b6f01c95ae76b939e4382950756ed41f0f6c9e` | [View](https://stellar.expert/explorer/testnet/tx/38cefe28249dc4584e16ad0a99b6f01c95ae76b939e4382950756ed41f0f6c9e) |
| 2 | Friendbot funding (USDC issuer) | `32865b2b03f2bb3182676100c5812e10121c521cd8e2b94d7c4690b35b2eaa60` | [View](https://stellar.expert/explorer/testnet/tx/32865b2b03f2bb3182676100c5812e10121c521cd8e2b94d7c4690b35b2eaa60) |
| 3 | USDC trustline (ChangeTrust) | `7bc463a0cd3ac11002ab352c72aed8146f636fc39ab182ecc1bad2ad8aa2dd9d` | [View](https://stellar.expert/explorer/testnet/tx/7bc463a0cd3ac11002ab352c72aed8146f636fc39ab182ecc1bad2ad8aa2dd9d) |
| 4 | Mint 1,000 USDC to master | `48a1efa3935c0ccab40115ab5c36a6ba49fcdaac76c9fbb9be8785129b916f7c` | [View](https://stellar.expert/explorer/testnet/tx/48a1efa3935c0ccab40115ab5c36a6ba49fcdaac76c9fbb9be8785129b916f7c) |
| 5 | Batched channel creation (3 accounts) | `54de5a9d8b4941a02d66c539609bf1be200d1e41769006953af54b12a6fc443f` | [View](https://stellar.expert/explorer/testnet/tx/54de5a9d8b4941a02d66c539609bf1be200d1e41769006953af54b12a6fc443f) |
| 6 | ManageSellOffer (10 XLM @ 0.50 USDC) | `8e5733710c8212296825ad98958d961ec0b4bf7236b6d41826bb4b6117c55e63` | [View](https://stellar.expert/explorer/testnet/tx/8e5733710c8212296825ad98958d961ec0b4bf7236b6d41826bb4b6117c55e63) |
| 7 | ManageBuyOffer (5 XLM @ 0.30 USDC) | `015b078b086e5150d851e76ee003935e01c0ab9caa60b1772611c2fd283c5104` | [View](https://stellar.expert/explorer/testnet/tx/015b078b086e5150d851e76ee003935e01c0ab9caa60b1772611c2fd283c5104) |
| 8 | Cancel sell offer (offer 66279) | `c52f3bff39708fb9c54a5777cf95bb8d6d759608404b2de041cdf5da814e2e69` | [View](https://stellar.expert/explorer/testnet/tx/c52f3bff39708fb9c54a5777cf95bb8d6d759608404b2de041cdf5da814e2e69) |

## What Each Transaction Demonstrates

- **TX 1-2**: Account creation and funding via Friendbot
- **TX 3**: Trustline setup — required before receiving non-native assets
- **TX 4**: Asset issuance — issuer account sends USDC to the master trading account
- **TX 5**: Batched channel creation — single transaction with 3 `CreateAccount` operations, each funded with 2.0 XLM. This is the pattern described in our architecture doc Section 5.
- **TX 6**: Sell offer via channel account — channel 1 is the transaction source, master account is the operation source (note the two signers). Offer ID 66279 extracted from result XDR.
- **TX 7**: Buy offer via channel 2 — same source-separation pattern, different channel, demonstrating parallel submission capability.
- **TX 8**: Offer cancellation — `ManageSellOffer` with amount=0 targeting offer 66279. Demonstrates graceful lifecycle management.

## SDEX Offer IDs

| Offer ID | Type | Asset Pair | Status |
|----------|------|-----------|--------|
| 66279 | ManageSellOffer | XLM/USDC | Cancelled (TX 8) |
| 66280 | ManageBuyOffer | XLM/USDC | Open |
