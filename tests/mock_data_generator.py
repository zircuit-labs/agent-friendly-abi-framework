#!/usr/bin/env python3
"""
Mock data generator for Zircuit Agent testing framework.

This module provides functionality to generate mock enhanced ABIs for testing
when real data is not available. Since real enhanced ABIs are available in the
data directory, this module is mainly for fallback purposes.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any
from loguru import logger


class MockDataGenerator:
    """
    Generates mock enhanced ABIs for testing purposes.
    
    Note: This is primarily a fallback when real enhanced ABIs are not available.
    The actual Zircuit project has real enhanced ABIs in data/enhanced_abis/.
    """
    
    def __init__(self):
        self.mock_contracts = {
            "0xBridgeContractAddress001": {
                "contract_type": "bridge",
                "functions": ["deposit", "depositNative", "authorize", "owner", "transferOwnership"]
            },
            "0xNFTContractAddress002": {
                "contract_type": "nft", 
                "functions": ["mint", "safeTransferFrom", "updateMintFee", "initialize", "renounceOwnership"]
            },
            "0xMyTokenERC20Address003": {
                "contract_type": "erc20",
                "functions": ["transfer", "balanceOf", "approve", "transferFrom"]
            },
            "0xSafeContractAddress004": {
                "contract_type": "safe",
                "functions": ["getOwners", "addOwnerWithThreshold"]
            },
            "0xMulticallContractAddress005": {
                "contract_type": "multicall",
                "functions": ["aggregate", "aggregate3Value", "getEthBalance", "getCurrentBlockTimestamp"]
            },
            "0xUniswapV2RouterAddress006": {
                "contract_type": "uniswap_router",
                "functions": ["swapETHForExactTokens", "addLiquidityETH", "swapExactTokensForETH"]
            },
            "0xAllowanceTransferAddress007": {
                "contract_type": "permit2",
                "functions": ["permit"]
            }
        }
    
    def generate_mock_enhanced_abi(self, contract_address: str, contract_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a mock enhanced ABI for a contract.
        
        Args:
            contract_address: Contract address
            contract_info: Contract information including type and functions
            
        Returns:
            Mock enhanced ABI structure
        """
        functions = {}
        
        for func_name in contract_info["functions"]:
            # Create basic function metadata based on common patterns
            if func_name in ["deposit", "mint", "transfer"]:
                functions[func_name] = {
                    "description": f"Function to {func_name} tokens or assets",
                    "parameters": ["recipient", "amount"],
                    "returns": "bool",
                    "stateMutability": "nonpayable"
                }
            elif func_name in ["balanceOf", "owner", "getOwners"]:
                functions[func_name] = {
                    "description": f"View function to get {func_name} information",
                    "parameters": ["account"] if func_name == "balanceOf" else [],
                    "returns": "uint256" if func_name == "balanceOf" else "address",
                    "stateMutability": "view"
                }
            else:
                functions[func_name] = {
                    "description": f"Function {func_name} for contract operations",
                    "parameters": [],
                    "returns": "bool",
                    "stateMutability": "nonpayable"
                }
        
        return {
            "contract_id": f"mock_{contract_info['contract_type']}",
            "contract_address": contract_address,
            "enhanced_abi": {
                "functions": functions,
                "contract_type": contract_info["contract_type"],
                "description": f"Mock {contract_info['contract_type']} contract for testing"
            },
            "source_code_available": False,
            "processed_at": "mock_timestamp",
            "model_used": "mock_model"
        }
    
    def generate_mock_enhanced_abis(self, output_dir: str) -> bool:
        """
        Generate mock enhanced ABIs for all test contracts.
        
        Args:
            output_dir: Directory to save mock enhanced ABIs
            
        Returns:
            True if successful, False otherwise
        """
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            logger.info("Generating mock enhanced ABIs (fallback mode)")
            
            for contract_address, contract_info in self.mock_contracts.items():
                enhanced_abi = self.generate_mock_enhanced_abi(contract_address, contract_info)
                
                # Generate filename similar to real enhanced ABIs
                filename = f"mock_{contract_info['contract_type']}_{contract_address}.json"
                filepath = output_path / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(enhanced_abi, f, indent=2)
                
                logger.debug(f"Generated mock enhanced ABI: {filepath}")
            
            logger.info(f"Generated {len(self.mock_contracts)} mock enhanced ABIs")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate mock enhanced ABIs: {e}")
            return False
    
    def check_real_data_available(self, enhanced_abis_dir: str) -> bool:
        """
        Check if real enhanced ABIs are available.
        
        Args:
            enhanced_abis_dir: Directory to check for enhanced ABIs
            
        Returns:
            True if real data is available, False otherwise
        """
        try:
            abi_path = Path(enhanced_abis_dir)
            if not abi_path.exists():
                return False
            
            # Check for JSON files
            json_files = list(abi_path.glob("*.json"))
            
            if len(json_files) > 0:
                logger.info(f"Found {len(json_files)} real enhanced ABI files")
                return True
            else:
                logger.warning("Enhanced ABIs directory exists but contains no JSON files")
                return False
                
        except Exception as e:
            logger.error(f"Error checking for real enhanced ABIs: {e}")
            return False 