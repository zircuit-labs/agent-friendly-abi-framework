#!/usr/bin/env python3
"""
Pytest configuration for Zircuit Agent testing framework.
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path to import the agent
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_test_case():
    """Provide a sample test case for unit testing."""
    return {
        "test_case_id": "ZRC_TC_001",
        "description": "User wants to deposit a specific ERC20 token into the bridge.",
        "natural_language_query": "I want to deposit 150 units of token 0xTokenToDeposit into the bridge contract 0xBridgeContractAddress001.",
        "assumed_contract_id": "bridge_contract_001",
        "assumed_contract_address": "0xBridgeContractAddress001",
        "expected_rewritten_query": "Execute a deposit of 150 units of ERC20 token at address 0xTokenToDeposit into contract 0xBridgeContractAddress001.",
        "ground_truth_function_calls": {
            "function_calling": [
                {
                    "function_name": "deposit",
                    "parameters": {
                        "token": "0xTokenToDeposit",
                        "amount": "150000000000000000000"
                    },
                    "value": "0",
                    "reasoning": "The user intends to deposit a specific ERC20 token. The 'deposit' function is appropriate. Assumes 18 decimals for 0xTokenToDeposit."
                }
            ]
        }
    }


@pytest.fixture
def sample_agent_result():
    """Provide a sample agent result for testing metrics calculation."""
    return {
        "original_query": "I want to deposit 150 units of token 0xTokenToDeposit into the bridge contract 0xBridgeContractAddress001.",
        "rewritten_query": "Execute a deposit of 150 units of ERC20 token at address 0xTokenToDeposit into contract 0xBridgeContractAddress001.",
        "relevant_contracts": [
            {
                "address": "0xBridgeContractAddress001",
                "score": 15,
                "contract_id": "bridge_contract_001"
            }
        ],
        "selected_contract": {
            "address": "0xBridgeContractAddress001",
            "contract_id": "bridge_contract_001"
        },
        "function_calls": {
            "function_calling": [
                {
                    "function_name": "deposit",
                    "parameters": {
                        "token": "0xTokenToDeposit",
                        "amount": "150000000000000000000"
                    },
                    "value": "0",
                    "reasoning": "The user intends to deposit a specific ERC20 token."
                }
            ]
        },
        "success": True
    } 