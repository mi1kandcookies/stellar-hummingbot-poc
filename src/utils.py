"""
Utility helpers for Stellar amount conversion and asset encoding.

Stellar represents all amounts as fixed-point integers with 7 decimal places
(stroops).  1 XLM = 10,000,000 stroops.
"""

from decimal import Decimal, ROUND_DOWN, getcontext

from stellar_sdk import Asset

# ---------------------------------------------------------------------------
# Decimal context — Stellar uses 7 decimal places
# ---------------------------------------------------------------------------
STELLAR_PRECISION = 7
STROOP_MULTIPLIER = Decimal("10000000")  # 10^7

# Configure the default decimal context for Stellar precision
getcontext().prec = 28  # plenty of room for intermediate calculations


def to_stroops(amount: Decimal) -> int:
    """Convert a human-readable Decimal amount to integer stroops.

    Args:
        amount: Decimal value (e.g. Decimal("1.5")).

    Returns:
        Integer stroop value.
    """
    return int((amount * STROOP_MULTIPLIER).to_integral_value(rounding=ROUND_DOWN))


def from_stroops(stroops: int) -> Decimal:
    """Convert integer stroops to a human-readable Decimal.

    Args:
        stroops: Integer stroop value.

    Returns:
        Decimal amount with up to 7 decimal places.
    """
    return Decimal(stroops) / STROOP_MULTIPLIER


def stellar_amount_to_decimal(amount_str: str) -> Decimal:
    """Convert a Stellar amount string (e.g. '100.0000000') to Decimal.

    Args:
        amount_str: String amount as returned by Horizon.

    Returns:
        Decimal representation.
    """
    return Decimal(amount_str)


def decimal_to_stellar_amount(amount: Decimal) -> str:
    """Format a Decimal as a Stellar amount string with 7 decimal places.

    Args:
        amount: Decimal value.

    Returns:
        String formatted to 7 decimal places (e.g. '1.5000000').
    """
    return f"{amount:.7f}"


def asset_to_horizon_params(asset: Asset, prefix: str = "") -> dict:
    """Convert a stellar_sdk Asset to Horizon query parameters.

    Args:
        asset: The Asset to convert.
        prefix: Optional prefix for parameter names (e.g. 'selling_' or 'buying_').

    Returns:
        Dictionary of query parameters suitable for Horizon REST API calls.
    """
    if asset.is_native():
        return {f"{prefix}asset_type": "native"}
    else:
        return {
            f"{prefix}asset_type": "credit_alphanum4" if len(asset.code) <= 4 else "credit_alphanum12",
            f"{prefix}asset_code": asset.code,
            f"{prefix}asset_issuer": asset.issuer,
        }
