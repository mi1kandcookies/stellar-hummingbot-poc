"""
SDEX orderbook reader via Horizon REST API.

Fetches orderbook snapshots for any asset pair and formats them for display.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List

import aiohttp

from stellar_sdk import Asset

from .config import HORIZON_URL
from .utils import asset_to_horizon_params, stellar_amount_to_decimal

logger = logging.getLogger(__name__)


class OrderbookReader:
    """Reads and displays SDEX orderbook data from Horizon."""

    def __init__(self):
        self.horizon_url = HORIZON_URL

    async def fetch_orderbook(
        self,
        selling_asset: Asset,
        buying_asset: Asset,
        limit: int = 20,
    ) -> Dict[str, List[Dict[str, Decimal]]]:
        """Fetch an orderbook snapshot from Horizon.

        Args:
            selling_asset: The asset being sold (base asset).
            buying_asset: The asset being bought (counter asset).
            limit: Max number of price levels per side (default 20).

        Returns:
            Dict with 'bids' and 'asks', each a list of
            {"price": Decimal, "amount": Decimal} sorted by price.
        """
        params = {
            **asset_to_horizon_params(selling_asset, prefix="selling_"),
            **asset_to_horizon_params(buying_asset, prefix="buying_"),
            "limit": str(limit),
        }

        url = f"{self.horizon_url}/order_book"
        logger.info("Fetching orderbook: %s / %s (limit=%d)", _asset_label(selling_asset), _asset_label(buying_asset), limit)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error("Orderbook request failed (%d): %s", resp.status, text[:200])
                    return {"bids": [], "asks": []}

                data = await resp.json()

        bids = [
            {
                "price": stellar_amount_to_decimal(level["price"]),
                "amount": stellar_amount_to_decimal(level["amount"]),
            }
            for level in data.get("bids", [])
        ]

        asks = [
            {
                "price": stellar_amount_to_decimal(level["price"]),
                "amount": stellar_amount_to_decimal(level["amount"]),
            }
            for level in data.get("asks", [])
        ]

        logger.info("Orderbook fetched: %d bids, %d asks", len(bids), len(asks))
        return {"bids": bids, "asks": asks}

    @staticmethod
    def display_orderbook(
        bids: List[Dict[str, Decimal]],
        asks: List[Dict[str, Decimal]],
        levels: int = 10,
    ) -> str:
        """Pretty-print the top N levels of the orderbook.

        Args:
            bids: List of bid levels (sorted best-first by Horizon).
            asks: List of ask levels (sorted best-first by Horizon).
            levels: Number of levels to display per side.

        Returns:
            Formatted string representation of the orderbook.
        """
        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append(f"{'ORDERBOOK':^60}")
        lines.append("=" * 60)

        # Asks (reversed so lowest ask is at the bottom, near the spread)
        lines.append(f"{'--- ASKS (selling) ---':^60}")
        lines.append(f"  {'Price':>15}  {'Amount':>15}")
        lines.append(f"  {'-' * 15}  {'-' * 15}")

        display_asks = asks[:levels]
        for level in reversed(display_asks):
            lines.append(f"  {level['price']:>15.7f}  {level['amount']:>15.7f}")

        if not display_asks:
            lines.append(f"  {'(no asks)':^32}")

        lines.append(f"  {'--- SPREAD ---':^32}")

        # Bids
        lines.append(f"{'--- BIDS (buying) ---':^60}")
        lines.append(f"  {'Price':>15}  {'Amount':>15}")
        lines.append(f"  {'-' * 15}  {'-' * 15}")

        display_bids = bids[:levels]
        for level in display_bids:
            lines.append(f"  {level['price']:>15.7f}  {level['amount']:>15.7f}")

        if not display_bids:
            lines.append(f"  {'(no bids)':^32}")

        lines.append("=" * 60)

        # Spread calculation
        if display_asks and display_bids:
            best_ask = display_asks[0]["price"]
            best_bid = display_bids[0]["price"]
            spread = best_ask - best_bid
            spread_pct = (spread / best_ask * 100) if best_ask > 0 else Decimal("0")
            lines.append(f"  Spread: {spread:.7f} ({spread_pct:.4f}%)")
        lines.append("")

        output = "\n".join(lines)
        return output


def _asset_label(asset: Asset) -> str:
    """Human-readable label for an asset."""
    if asset.is_native():
        return "XLM"
    return f"{asset.code}:{asset.issuer[:8]}..."
