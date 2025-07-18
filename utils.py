import json
from web3 import Web3


def build_single_call_transaction(
        web3: Web3,
        target_address: str,
        target_abi: list,
        function_name: str,
        parameters: list,
        from_address: str,
        gas: int = 300000,
        gas_price_gwei: str = '50'
) -> dict:
    """
    Builds an unsigned transaction dictionary for a single function call to a contract.

    Parameters:
      web3: A Web3 instance connected to an Ethereum node.
      target_address: The address of the target contract.
      target_abi: The ABI of the target contract.
      function_name: The name of the function to call.
      parameters: A list of parameters for the function call.
      from_address: The sender's address (must hold ETH for gas).
      gas: The gas limit for the transaction.
      gas_price_gwei: The gas price in gwei.

    Returns:
      An unsigned transaction dictionary ready for signing and sending.
    """
    # Create a contract instance
    contract = web3.eth.contract(address=target_address, abi=target_abi)

    # Get the current nonce for the sender's address
    nonce = web3.eth.get_transaction_count(from_address)

    # Build the transaction using the specified function and parameters
    tx = contract.functions[function_name](*parameters).build_transaction({
        'from': from_address,
        'nonce': nonce,
        'gas': gas,
        'gasPrice': web3.to_wei(gas_price_gwei, 'gwei')
    })

    return tx


# Example usage:
if __name__ == "__main__":
    # Connect to an Ethereum node (for example, via Infura)
    web3 = Web3(Web3.HTTPProvider("https://shape-mainnet.g.alchemy.com/v2/96UGLH6QQCIVKoiSYMwsOQlj0SkRX_bO"))

    # Target contract details
    target_abi = json.load(open("./uniswap_v2_factory.json"))["abi"]
    target_address = "<address>"
    target_contract = web3.eth.contract(address=target_address, abi=target_abi)

    token_a = "<address>"
    token_b = "<address>"
    # Build the transaction without signing or sending
    built_tx = build_single_call_transaction(
        web3,
        target_address,
        target_abi,
        "createPair",
        [token_a, token_b],
        token_a,
    )

    print("Built Transaction:")
    print(built_tx)
