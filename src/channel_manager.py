"""
Channel account pool for parallel transaction submission.

Channel accounts allow a single logical trader to submit multiple transactions
concurrently without sequence-number conflicts.  Each channel is a separate
Stellar account whose sole purpose is to act as the transaction source while
the master account remains the owner of all offers and trustlines.
"""

import asyncio
import logging
from decimal import Decimal
from typing import List, Optional

import aiohttp
from stellar_sdk import (
    Account,
    Asset,
    Keypair,
    Server,
    TransactionBuilder,
)
from stellar_sdk.operation import CreateAccount, Payment

from .config import (
    BASE_FEE,
    FRIENDBOT_URL,
    HORIZON_URL,
    NETWORK_PASSPHRASE,
)
from .utils import stellar_amount_to_decimal

logger = logging.getLogger(__name__)

# Minimum balance before a channel is replenished
REPLENISH_THRESHOLD = Decimal("1.5")
# Target balance after replenishment
REPLENISH_TARGET = Decimal("2.0")
# Initial funding amount per channel
INITIAL_FUND_AMOUNT = "2.0"


class ChannelManager:
    """Manages a pool of channel accounts for concurrent tx submission.

    Attributes:
        master_keypair: The master trading account keypair.
        server: Horizon Server instance.
        channels: List of channel Keypairs.
        _available: asyncio.Queue of available channel Keypairs.
        _lock: asyncio.Lock guarding mutations.
    """

    def __init__(self, master_keypair: Keypair, server: Server, num_channels: int = 3):
        self.master_keypair = master_keypair
        self.server = server
        self.num_channels = num_channels
        self.channels: List[Keypair] = []
        self._available: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        # Local sequence number cache: public_key -> last known sequence
        self._sequences: dict[str, int] = {}

    async def fund_master_from_friendbot(self) -> str:
        """Fund the master account using the Stellar testnet Friendbot.

        Returns:
            Transaction hash from the Friendbot funding.
        """
        url = f"{FRIENDBOT_URL}?addr={self.master_keypair.public_key}"
        logger.info("Requesting Friendbot funding for %s", self.master_keypair.public_key)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                result = await resp.json()
                if resp.status != 200:
                    # Friendbot may return 400 if already funded - that's OK
                    if "already exists" in str(result).lower() or "createAccountAlreadyExist" in str(result):
                        logger.info("Master account already funded")
                        return "already_funded"
                    raise RuntimeError(f"Friendbot failed: {result}")
                tx_hash = result.get("hash", result.get("id", "unknown"))
                logger.info("Friendbot funded master account. TX: %s", tx_hash)
                return tx_hash

    async def create_channels(self) -> str:
        """Create and fund channel accounts in a single batched transaction.

        Each channel is funded with INITIAL_FUND_AMOUNT XLM from the master
        account using a CreateAccount operation.

        Returns:
            Transaction hash of the channel-creation transaction.
        """
        # Generate channel keypairs
        self.channels = [Keypair.random() for _ in range(self.num_channels)]

        # Load master account from Horizon to get current sequence
        master_account = self.server.load_account(self.master_keypair.public_key)

        # Build a single transaction with one CreateAccount op per channel
        builder = TransactionBuilder(
            source_account=master_account,
            network_passphrase=NETWORK_PASSPHRASE,
            base_fee=BASE_FEE,  # per-operation; SDK multiplies by op count
        )
        builder.set_timeout(30)

        for ch_kp in self.channels:
            builder.append_operation(
                CreateAccount(
                    destination=ch_kp.public_key,
                    starting_balance=INITIAL_FUND_AMOUNT,
                )
            )
            logger.info("  Channel account: %s", ch_kp.public_key)

        tx = builder.build()
        tx.sign(self.master_keypair)

        response = self.server.submit_transaction(tx)
        tx_hash = response["hash"]
        logger.info("Channels created in TX: %s", tx_hash)

        # Populate the available-channel queue and cache sequences
        for ch_kp in self.channels:
            ch_account = self.server.load_account(ch_kp.public_key)
            self._sequences[ch_kp.public_key] = int(ch_account.sequence)
            await self._available.put(ch_kp)

        return tx_hash

    async def acquire_channel(self) -> Keypair:
        """Acquire an available channel account from the pool.

        Blocks until a channel is available.

        Returns:
            Keypair of the acquired channel.
        """
        channel = await self._available.get()
        logger.debug("Acquired channel %s", channel.public_key)
        return channel

    async def release_channel(self, channel_keypair: Keypair) -> None:
        """Return a channel account to the pool.

        Args:
            channel_keypair: The channel Keypair to release.
        """
        # Refresh the sequence number from the network after use
        try:
            ch_account = self.server.load_account(channel_keypair.public_key)
            self._sequences[channel_keypair.public_key] = int(ch_account.sequence)
        except Exception as exc:
            logger.warning("Could not refresh sequence for %s: %s", channel_keypair.public_key, exc)

        await self._available.put(channel_keypair)
        logger.debug("Released channel %s", channel_keypair.public_key)

    def get_account(self, channel_keypair: Keypair) -> Account:
        """Build an Account object with the locally cached sequence number.

        Args:
            channel_keypair: The channel Keypair.

        Returns:
            Account instance for TransactionBuilder.
        """
        seq = self._sequences.get(channel_keypair.public_key, 0)
        return Account(channel_keypair.public_key, seq)

    async def replenish_channels(self) -> Optional[str]:
        """Check channel balances and top up any below REPLENISH_THRESHOLD.

        Sends a single transaction with Payment operations for all channels
        that need replenishment.

        Returns:
            Transaction hash if replenishment was performed, None otherwise.
        """
        async with self._lock:
            channels_to_fund: list[tuple[Keypair, Decimal]] = []

            for ch_kp in self.channels:
                try:
                    acct_info = self.server.accounts().account_id(ch_kp.public_key).call()
                    native_balance = Decimal("0")
                    for bal in acct_info["balances"]:
                        if bal["asset_type"] == "native":
                            native_balance = stellar_amount_to_decimal(bal["balance"])
                            break

                    if native_balance < REPLENISH_THRESHOLD:
                        top_up = REPLENISH_TARGET - native_balance
                        channels_to_fund.append((ch_kp, top_up))
                        logger.info(
                            "Channel %s balance %.2f XLM - needs replenishment of %.2f",
                            ch_kp.public_key[:8],
                            native_balance,
                            top_up,
                        )
                except Exception as exc:
                    logger.warning("Could not check channel %s: %s", ch_kp.public_key[:8], exc)

            if not channels_to_fund:
                logger.info("All channels above replenishment threshold")
                return None

            # Check master account balance before attempting replenishment
            try:
                master_info = self.server.accounts().account_id(self.master_keypair.public_key).call()
                master_native = Decimal("0")
                for bal in master_info["balances"]:
                    if bal["asset_type"] == "native":
                        master_native = stellar_amount_to_decimal(bal["balance"])
                        break

                total_needed = sum(amount for _, amount in channels_to_fund)
                # Reserve: base reserve (1 XLM) + 0.5 per subentry + some margin
                min_master_balance = Decimal("5.0")
                if master_native - total_needed < min_master_balance:
                    logger.warning(
                        "Master account balance (%.2f XLM) insufficient to replenish "
                        "channels (need %.2f XLM, minimum reserve %.2f XLM). Skipping.",
                        master_native,
                        total_needed,
                        min_master_balance,
                    )
                    return None
            except Exception as exc:
                logger.warning("Could not check master balance: %s. Skipping replenishment.", exc)
                return None

            # Build replenishment transaction
            master_account = self.server.load_account(self.master_keypair.public_key)
            builder = TransactionBuilder(
                source_account=master_account,
                network_passphrase=NETWORK_PASSPHRASE,
                base_fee=BASE_FEE,
            )
            builder.set_timeout(30)

            for ch_kp, amount in channels_to_fund:
                builder.append_operation(
                    Payment(
                        destination=ch_kp.public_key,
                        asset=Asset.native(),
                        amount=f"{amount:.7f}",
                    )
                )

            tx = builder.build()
            tx.sign(self.master_keypair)

            response = self.server.submit_transaction(tx)
            tx_hash = response["hash"]
            logger.info("Replenished %d channels in TX: %s", len(channels_to_fund), tx_hash)
            return tx_hash
