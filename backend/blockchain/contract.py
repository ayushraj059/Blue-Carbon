import os
import json
import logging
import hashlib
from pathlib import Path
from web3 import Web3
try:
    from web3.middleware import ExtraDataToPOAMiddleware as _poa_mw  # web3 v7+
except ImportError:
    from web3.middleware import geth_poa_middleware as _poa_mw  # web3 v6

logger = logging.getLogger(__name__)

_w3 = None
_contract = None

FALLBACK_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "_projectId", "type": "string"},
            {"internalType": "uint256", "name": "_carbonTons", "type": "uint256"},
            {"internalType": "bytes32", "name": "_verificationHash", "type": "bytes32"},
        ],
        "name": "registerCredit",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "string", "name": "_projectId", "type": "string"}],
        "name": "getCredit",
        "outputs": [
            {"internalType": "string", "name": "projectId", "type": "string"},
            {"internalType": "uint256", "name": "carbonTons", "type": "uint256"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"internalType": "bytes32", "name": "verificationHash", "type": "bytes32"},
            {"internalType": "bool", "name": "verificationStatus", "type": "bool"},
            {"internalType": "address", "name": "registeredBy", "type": "address"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getAllProjectIds",
        "outputs": [{"internalType": "string[]", "name": "", "type": "string[]"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getTotalCredits",
        "outputs": [
            {"internalType": "uint256", "name": "count", "type": "uint256"},
            {"internalType": "uint256", "name": "totalTons", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


def _load_abi() -> list:
    abi_paths = [
        Path(__file__).parent / "CarbonRegistry_abi.json",
        Path(__file__).parent.parent.parent / "contracts" / "artifacts" / "CarbonRegistry.sol" / "CarbonRegistry.json",
    ]
    for path in abi_paths:
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return data.get("abi", FALLBACK_ABI)
    logger.warning("ABI file not found, using fallback ABI")
    return FALLBACK_ABI


def _load_contract_address() -> str:
    address = os.getenv("CONTRACT_ADDRESS", "")
    if address:
        return address

    addr_paths = [
        Path(__file__).parent.parent.parent / "contracts" / "deployed_address.json",
    ]
    for path in addr_paths:
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return data.get("address", "")

    return ""


def get_web3() -> Web3:
    global _w3
    if _w3 is None:
        rpc_url = os.getenv("ALCHEMY_RPC_URL", "")
        if not rpc_url:
            raise ValueError("ALCHEMY_RPC_URL not configured")
        _w3 = Web3(Web3.HTTPProvider(rpc_url))
        _w3.middleware_onion.inject(_poa_mw, layer=0)
        if not _w3.is_connected():
            raise ConnectionError("Cannot connect to blockchain RPC")
    return _w3


def get_contract():
    global _contract
    if _contract is None:
        w3 = get_web3()
        address = _load_contract_address()
        if not address:
            raise ValueError("CONTRACT_ADDRESS not configured")
        abi = _load_abi()
        _contract = w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)
    return _contract


def _is_demo_mode() -> bool:
    """Demo mode: contract not yet deployed or private key is a placeholder."""
    pk = os.getenv("DEPLOYER_PRIVATE_KEY", "")
    addr = os.getenv("CONTRACT_ADDRESS", "")
    pk_clean = pk.lstrip("0x").lstrip("0")
    addr_clean = addr.lstrip("0x").lstrip("0")
    return not pk_clean or not addr_clean


def register_credit(project_id: str, carbon_tons: float, verification_hash: str) -> dict:
    if _is_demo_mode():
        import hashlib, time
        fake_hash = "0x" + hashlib.sha256(f"{project_id}{carbon_tons}{time.time()}".encode()).hexdigest()
        logger.warning(f"[DEMO MODE] Blockchain not configured — returning mock TX for {project_id}")
        return {
            "tx_hash": fake_hash,
            "block_number": 12345678,
            "status": "success",
            "gas_used": 85000,
            "demo_mode": True,
        }

    try:
        w3 = get_web3()
        contract = get_contract()

        private_key = os.getenv("DEPLOYER_PRIVATE_KEY", "")
        if not private_key:
            raise ValueError("DEPLOYER_PRIVATE_KEY not set")

        if not private_key.startswith("0x"):
            private_key = "0x" + private_key

        account = w3.eth.account.from_key(private_key)
        carbon_tons_int = int(carbon_tons * 1000)
        hash_bytes = bytes.fromhex(
            hashlib.sha256(verification_hash.encode()).hexdigest()
        )

        nonce = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price

        txn = contract.functions.registerCredit(
            project_id, carbon_tons_int, hash_bytes
        ).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gasPrice": gas_price,
            "gas": 300000,
        })

        signed = w3.eth.account.sign_transaction(txn, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        return {
            "tx_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "status": "success" if receipt.status == 1 else "failed",
            "gas_used": receipt.gasUsed,
        }

    except Exception as e:
        logger.error(f"Blockchain registration failed: {e}")
        raise


def get_credit_from_chain(project_id: str) -> dict:
    try:
        contract = get_contract()
        result = contract.functions.getCredit(project_id).call()
        return {
            "project_id": result[0],
            "carbon_tons": result[1] / 1000.0,
            "timestamp": result[2],
            "verification_hash": result[3].hex(),
            "verification_status": result[4],
            "registered_by": result[5],
        }
    except Exception as e:
        logger.error(f"Failed to fetch credit from chain: {e}")
        raise
