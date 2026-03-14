"""
Stellar testnet configuration and keypair management.

Provides centralized configuration for Horizon endpoints, network passphrase,
asset definitions, and keypair loading for the SDEX proof of concept.
"""

import os
import logging

from stellar_sdk import Asset, Keypair, Network

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Network endpoints
# ---------------------------------------------------------------------------
HORIZON_URL = "https://horizon-testnet.stellar.org"
FRIENDBOT_URL = "https://friendbot.stellar.org"
NETWORK_PASSPHRASE = Network.TESTNET_NETWORK_PASSPHRASE  # "Test SDF Network ; September 2015"

# ---------------------------------------------------------------------------
# Fee configuration
# ---------------------------------------------------------------------------
BASE_FEE = 100  # stroops

# ---------------------------------------------------------------------------
# Asset definitions
# ---------------------------------------------------------------------------
XLM = Asset.native()

# USDC is created dynamically on testnet - there is no canonical issuer.
# The demo creates its own issuer account and mints test USDC.
# This variable is set at runtime by demo.py after issuer creation.
USDC = None
USDC_CODE = "USDC"

# ---------------------------------------------------------------------------
# Keypair loading
# ---------------------------------------------------------------------------

def load_keypair() -> Keypair:
    """Load the master keypair from the STELLAR_SECRET_KEY env var.

    If the environment variable is not set, a fresh random keypair is
    generated so the demo can still run on testnet via Friendbot funding.

    Returns:
        Keypair instance for the master account.
    """
    secret = os.environ.get("STELLAR_SECRET_KEY")
    if secret:
        kp = Keypair.from_secret(secret)
        logger.info("Loaded keypair from STELLAR_SECRET_KEY: %s", kp.public_key)
    else:
        kp = Keypair.random()
        logger.info("Generated new random keypair: %s", kp.public_key)
        logger.info("Secret key (save if you want to reuse): %s", kp.secret)
    return kp
