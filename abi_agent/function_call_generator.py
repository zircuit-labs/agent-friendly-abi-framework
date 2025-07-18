import json
import sys
import traceback
from typing import Dict, List, Any

from watchfiles import awatch

from llm_generation.task_processor import TaskProcessor
import asyncio
from loguru import logger

class FunctionCallGenerator:

    def __init__(self, model_name: str = 'o3-mini'):
        self.model_name = model_name
        self.task_processor = TaskProcessor(
            prompt_template_config_path="./prompt_template/convert_query_to_function_calling.yml",
            model_name=model_name
        )

    def _create_focused_abi(self, 
                           enhanced_abis: Dict[str, Dict],
                           selected_contracts: List[str]) -> str:
        """
        Create a focused ABI containing only the selected contracts.
        
        Args:
            enhanced_abis: Full enhanced ABIs dictionary
            selected_contracts: List of selected contract addresses
            
        Returns:
            JSON string of focused ABI content
        """
        focused_abis = {}
        
        for contract_address in selected_contracts:
            if contract_address in enhanced_abis:
                contract_data = enhanced_abis[contract_address]
                # The enhanced ABI data is at the root level under 'enhanced_abi' key
                enhanced_abi_data = contract_data.get('enhanced_abi', {})
                
                # Filter to only include function entries
                functions = {}
                for key, value in enhanced_abi_data.items():
                    if isinstance(value, dict) and (
                        'stateMutability' in value or 
                        'inputs' in value or 
                        'parameters' in value or
                        'name' in value
                    ):
                        functions[key] = value
                
                focused_abis[contract_address] = {
                    'contract_address': contract_address,
                    'contract_id': contract_data.get('contract_id', 'unknown'),
                    'functions': functions,
                    'events': {}  # Could extract events similarly if needed
                }
            else:
                logger.warning(f"Selected contract {contract_address} not found in enhanced ABIs")
        
        return json.dumps(focused_abis, indent=2)

    async def generate_from_multiple_contracts(self, 
                                             user_query: str, 
                                             enhanced_abis: Dict[str, Dict],
                                             selected_contracts: List[str]):
        """
        Generate function calls from multiple pre-selected contracts.
        
        Args:
            user_query: Natural language query from user
            enhanced_abis: Full enhanced ABIs dictionary  
            selected_contracts: List of pre-selected contract addresses
            
        Returns:
            Function call generation result
        """
        try:
            logger.info(f"Generating function calls for query: {user_query}")
            logger.info(f"Using {len(selected_contracts)} pre-selected contracts: {selected_contracts}")
            
            # Create focused ABI content with only selected contracts
            focused_abi_content = self._create_focused_abi(enhanced_abis, selected_contracts)
            
            logger.debug(f"Focused ABI content length: {len(focused_abi_content)} characters")
            
            result = await self.task_processor.run(
                user_query=user_query, 
                abi_content=focused_abi_content, 
                is_json=True
            )
            
            logger.info(f'Generated raw content: {result}')
            
            # Validate the result structure
            if not isinstance(result, dict):
                logger.error(f"Expected dict result, got {type(result)}: {result}")
                return {"function_calling": [], "error": "Invalid result format"}
            
            if "function_calling" not in result:
                logger.error(f"Missing 'function_calling' key in result: {result}")
                return {"function_calling": [], "error": "Missing function_calling key"}
            
            if not isinstance(result["function_calling"], list):
                logger.error(f"Expected list for function_calling, got {type(result['function_calling'])}")
                return {"function_calling": [], "error": "Invalid function_calling format"}
            
            # Validate each function call
            for i, func_call in enumerate(result["function_calling"]):
                if not isinstance(func_call, dict):
                    logger.error(f"Function call {i} is not a dict: {func_call}")
                    continue
                
                required_keys = ["function_name", "parameters", "pre_condition", "reasoning"]
                missing_keys = [key for key in required_keys if key not in func_call]
                if missing_keys:
                    logger.warning(f"Function call {i} missing keys: {missing_keys}")
                
                # Validate function_name
                if "function_name" in func_call and not isinstance(func_call["function_name"], str):
                    logger.warning(f"Function call {i} has non-string function_name: {func_call['function_name']}")
                
                # Validate parameters
                if "parameters" in func_call and not isinstance(func_call["parameters"], list):
                    logger.warning(f"Function call {i} has non-list parameters: {func_call['parameters']}")
            
            # Add contract selection information to the result
            result['selected_contracts'] = selected_contracts
            result['contracts_used'] = len(selected_contracts)
            
            logger.success(f"Successfully generated {len(result['function_calling'])} function calls from {len(selected_contracts)} contracts")
            return result
            
        except Exception as e:
            logger.error(f"Error generating function calls: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "function_calling": [], 
                "error": f"Generation failed: {str(e)}",
                "selected_contracts": selected_contracts
            }

    async def generate(self, user_query: str, abi_content: str):
        """
        Original single-contract generation method (maintained for backward compatibility).
        
        Args:
            user_query: Natural language query from user
            abi_content: ABI content as JSON string
            
        Returns:
            Function call generation result
        """
        try:
            logger.info(f"Generating function calls for query: {user_query}")
            logger.debug(f"ABI content length: {len(abi_content)} characters")
            
            # Ensure proper formatting of inputs
            if isinstance(abi_content, str):
                try:
                    # Try to parse and re-stringify to ensure valid JSON
                    parsed_abi = json.loads(abi_content)
                    abi_content = json.dumps(parsed_abi, indent=2)
                except json.JSONDecodeError:
                    logger.warning("ABI content is not valid JSON, using as-is")
            
            result = await self.task_processor.run(
                user_query=user_query, 
                abi_content=abi_content, 
                is_json=True
            )
            
            logger.info(f'Generated raw content: {result}')
            
            # Validate the result structure
            if not isinstance(result, dict):
                logger.error(f"Expected dict result, got {type(result)}: {result}")
                return {"function_calling": [], "error": "Invalid result format"}
            
            if "function_calling" not in result:
                logger.error(f"Missing 'function_calling' key in result: {result}")
                return {"function_calling": [], "error": "Missing function_calling key"}
            
            if not isinstance(result["function_calling"], list):
                logger.error(f"Expected list for function_calling, got {type(result['function_calling'])}")
                return {"function_calling": [], "error": "Invalid function_calling format"}
            
            # Validate each function call
            for i, func_call in enumerate(result["function_calling"]):
                if not isinstance(func_call, dict):
                    logger.error(f"Function call {i} is not a dict: {func_call}")
                    continue
                
                required_keys = ["function_name", "parameters", "pre_condition", "reasoning"]
                missing_keys = [key for key in required_keys if key not in func_call]
                if missing_keys:
                    logger.warning(f"Function call {i} missing keys: {missing_keys}")
                
                # Validate function_name
                if "function_name" in func_call and not isinstance(func_call["function_name"], str):
                    logger.warning(f"Function call {i} has non-string function_name: {func_call['function_name']}")
                
                # Validate parameters
                if "parameters" in func_call and not isinstance(func_call["parameters"], list):
                    logger.warning(f"Function call {i} has non-list parameters: {func_call['parameters']}")
            
            logger.success(f"Successfully generated {len(result['function_calling'])} function calls")
            return result
            
        except Exception as e:
            logger.error(f"Error generating function calls: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "function_calling": [], 
                "error": f"Generation failed: {str(e)}"
            }

if __name__ == '__main__':
    async def test_main():
        generator = FunctionCallGenerator()
        abi_content = """{
          "addOwnerWithThreshold": {
            "name": "addOwnerWithThreshold",
            "description": "A state-modifying function that executes addOwnerWithThreshold on the blockchain. Takes 2 parameters.",
            "parameters": [
              {
                "name": "owner",
                "type": "address",
                "description": "The owner address for addOwnerWithThreshold."
              },
              {
                "name": "_threshold",
                "type": "uint256",
                "description": "An unsigned integer parameter for addOwnerWithThreshold."
              }
            ]
          }
        }"""
        result = await generator.generate(
            user_query="I want to add a new owner 0x1234567890abcdef1234567890abcdef12345678 with threshold 2",
            abi_content=abi_content
        )
        print(json.dumps(result, indent=2))
    
    asyncio.run(test_main())