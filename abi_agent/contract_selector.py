import json
import asyncio
from typing import Dict, List, Any
from loguru import logger

from llm_generation.task_processor import TaskProcessor


class ContractSelector:
    """
    First-stage contract selector that uses simplified ABIs to shortlist 
    relevant contracts based on user queries.
    """
    
    def __init__(self, model_name: str = 'o3-mini'):
        self.model_name = model_name
        self.task_processor = TaskProcessor(
            prompt_template_config_path="./prompt_template/select_contracts.yml",
            model_name=model_name
        )
    
    def create_simplified_abi(self, enhanced_abi: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a simplified version of an enhanced ABI for initial contract selection.
        
        Args:
            enhanced_abi: Full enhanced ABI dictionary
            
        Returns:
            Simplified ABI with just essential information
        """
        simplified = {
            'contract_info': {},
            'functions': {},
            'function_count': 0,
            'categories': []
        }
        
        # Extract contract metadata if available
        if 'contract_info' in enhanced_abi:
            simplified['contract_info'] = enhanced_abi['contract_info']
        
        # Extract functions with minimal info
        # The enhanced_abi structure has functions at the root level under 'enhanced_abi' key
        enhanced_abi_data = enhanced_abi.get('enhanced_abi', enhanced_abi)
        
        # Filter out non-function entries (like contract_info, etc.) and extract actual functions
        for key, value in enhanced_abi_data.items():
            # Check if this is a function entry (has typical function properties)
            if isinstance(value, dict) and (
                'stateMutability' in value or 
                'inputs' in value or 
                'parameters' in value or
                'name' in value
            ):
                simplified['functions'][key] = {
                    'name': key,
                    'description': value.get('description', '')[:200],  # Truncate long descriptions
                    'type': 'function',
                    'parameter_count': len(value.get('parameters', value.get('inputs', [])))
                }
        
        simplified['function_count'] = len(simplified['functions'])
        
        # Infer categories based on function names
        simplified['categories'] = self._infer_categories(list(simplified['functions'].keys()))
        
        return simplified
    
    def _infer_categories(self, function_names: List[str]) -> List[str]:
        """
        Infer contract categories based on function names.
        """
        categories = set()
        
        # Define category patterns
        category_patterns = {
            'multisig': ['addowner', 'removeowner', 'swapowner', 'changethreshold', 'getowners'],
            'erc20': ['transfer', 'approve', 'allowance', 'balanceof', 'totalsupply'],
            'erc721': ['mint', 'burn', 'tokenuri', 'ownerof', 'approve', 'transferfrom'],
            'bridge': ['deposit', 'withdraw', 'bridge', 'relay'],
            'swap': ['swap', 'addliquidity', 'removeliquidity', 'getamountout'],
            'vault': ['stake', 'unstake', 'reward', 'harvest'],
            'governance': ['propose', 'vote', 'execute', 'cancel'],
            'multicall': ['multicall', 'aggregate', 'tryaggregate'],
            'proxy': ['upgrade', 'implementation', 'admin'],
            'pausable': ['pause', 'unpause', 'paused'],
            'ownable': ['owner', 'transferownership', 'renounceownership']
        }
        
        func_names_lower = [name.lower() for name in function_names]
        
        for category, patterns in category_patterns.items():
            if any(pattern in ' '.join(func_names_lower) for pattern in patterns):
                categories.add(category)
        
        return list(categories)
    
    async def select_contracts(self, 
                             user_query: str, 
                             enhanced_abis: Dict[str, Dict],
                             max_contracts: int = 3) -> List[str]:
        """
        Select the most relevant contracts for a user query using simplified ABIs.
        
        Args:
            user_query: Natural language query from user
            enhanced_abis: Dictionary mapping contract addresses to enhanced ABIs
            max_contracts: Maximum number of contracts to select
            
        Returns:
            List of selected contract addresses/IDs
        """
        logger.info(f"Selecting contracts for query: {user_query}")
        logger.info(f"Evaluating {len(enhanced_abis)} contracts")
        
        # Create simplified ABIs
        simplified_abis = {}
        for contract_address, enhanced_abi in enhanced_abis.items():
            simplified_abis[contract_address] = self.create_simplified_abi(enhanced_abi)
        
        try:
            # Format simplified ABIs for the LLM
            simplified_abis_json = json.dumps(simplified_abis, indent=2)
            
            result = await self.task_processor.run(
                user_query=user_query,
                simplified_abis=simplified_abis_json,
                max_contracts=max_contracts,
                is_json=True
            )
            
            logger.info(f"Contract selection result: {result}")
            
            # Validate result
            if not isinstance(result, dict) or 'selected_contracts' not in result:
                logger.error(f"Invalid contract selection result: {result}")
                return []
            
            selected_contracts = result['selected_contracts']
            if not isinstance(selected_contracts, list):
                logger.error(f"Expected list for selected_contracts, got: {type(selected_contracts)}")
                return []
            
            # Extract contract addresses from result
            contract_addresses = []
            for contract in selected_contracts:
                if isinstance(contract, dict) and 'contract_address' in contract:
                    contract_addresses.append(contract['contract_address'])
                elif isinstance(contract, str):
                    contract_addresses.append(contract)
            
            logger.success(f"Selected {len(contract_addresses)} contracts: {contract_addresses}")
            return contract_addresses[:max_contracts]
            
        except Exception as e:
            logger.error(f"Error in contract selection: {e}")
            # Fallback to simple keyword matching
            return self._fallback_selection(user_query, enhanced_abis, max_contracts)
    
    def _fallback_selection(self, 
                          user_query: str, 
                          enhanced_abis: Dict[str, Dict],
                          max_contracts: int) -> List[str]:
        """
        Fallback contract selection using simple keyword matching.
        """
        logger.info("Using fallback contract selection")
        
        query_lower = user_query.lower()
        scored_contracts = []
        
        for contract_address, contract_data in enhanced_abis.items():
            score = 0
            # Get the enhanced ABI data
            enhanced_abi_data = contract_data.get('enhanced_abi', contract_data)
            
            # Score based on function name matches
            for func_name, func_data in enhanced_abi_data.items():
                # Check if this is a function entry
                if isinstance(func_data, dict) and (
                    'stateMutability' in func_data or 
                    'inputs' in func_data or 
                    'parameters' in func_data or
                    'name' in func_data
                ):
                    func_name_lower = func_name.lower()
                    description = func_data.get('description', '').lower()
                    
                    # Simple keyword matching
                    for word in query_lower.split():
                        if len(word) > 2:  # Skip very short words
                            if word in func_name_lower:
                                score += 3
                            if word in description:
                                score += 1
            
            if score > 0:
                scored_contracts.append((contract_address, score))
        
        # Sort by score and return top contracts
        scored_contracts.sort(key=lambda x: x[1], reverse=True)
        return [addr for addr, _ in scored_contracts[:max_contracts]]


if __name__ == '__main__':
    async def test_main():
        selector = ContractSelector()
        
        # Test with mock data
        mock_enhanced_abis = {
            "0x123": {
                "functions": {
                    "addOwner": {
                        "description": "Add a new owner to the multisig wallet",
                        "parameters": [{"name": "owner", "type": "address"}]
                    },
                    "removeOwner": {
                        "description": "Remove an owner from the multisig wallet", 
                        "parameters": [{"name": "owner", "type": "address"}]
                    }
                }
            },
            "0x456": {
                "functions": {
                    "transfer": {
                        "description": "Transfer tokens to another address",
                        "parameters": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}]
                    }
                }
            }
        }
        
        result = await selector.select_contracts(
            "I want to add a new owner to the multisig",
            mock_enhanced_abis
        )
        print(f"Selected contracts: {result}")
    
    asyncio.run(test_main()) 