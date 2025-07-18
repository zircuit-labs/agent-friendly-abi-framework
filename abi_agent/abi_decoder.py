import json
import asyncio
from typing import Dict, List, Any, Optional
from loguru import logger
from collections import defaultdict

from llm_generation.task_processor import TaskProcessor


class ABIDecoder:
    """
    Enhanced ABI Decoder optimized for Zircuit smart contracts.
    Generates LLM-friendly ABI formats with comprehensive function documentation,
    parameter descriptions, and usage examples tailored for Zircuit blockchain.
    """

    def __init__(self, model_name: str = 'o3-mini',
                 prompt_template_path: str = 'prompt_template/decode_abi.yml'):
        self.model_name = model_name
        self.prompt_template_path = prompt_template_path
        self.task_processor = TaskProcessor(
            prompt_template_config_path=prompt_template_path,
            model_name=model_name
        )
        
        # Zircuit-specific token addresses and common patterns (Updated for mainnet)
        self.zircuit_tokens = self._get_zircuit_tokens()
        self.zircuit_patterns = self._get_zircuit_patterns()

    def _get_zircuit_tokens(self) -> Dict[str, str]:
        """Get common Zircuit token addresses and information."""
        return {
            # Native and wrapped tokens
            'ETH': '0x0000000000000000000000000000000000000000',  # Native ETH
            'WETH': '0x4200000000000000000000000000000000000006',  # Wrapped ETH on Zircuit
            'ZRC': '0xZRC_TOKEN_ADDRESS_PLACEHOLDER',  # ZRC token (to be updated)
            
            # Bridged stablecoin addresses (Examples - need to be updated with actual Zircuit addresses)
            'USDC': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',  # USDC
            'USDT': '0xdac17f958d2ee523a2206206994597c13d831ec7',  # USDT
            'DAI': '0x6b175474e89094c44da98b954eedeac495271d0f',   # DAI
            
            # LST/LRT tokens (Liquid Staking Tokens)
            'stETH': '0xae7ab96520de3a18e5e111b5eaab095312d7fe84', # Lido stETH
            'rETH': '0xae78736cd615f374d3085123a210448e74fc6393',  # RocketPool ETH
            'cbETH': '0xbe9895146f7af43049ca1c1ae358b0541ea49704', # Coinbase ETH
            'sfrxETH': '0xac3e018457b222d93114458476f3e3416abbe38f', # Frax ETH
            
            # Zircuit ecosystem tokens (placeholders)
            'AFFINE': '0xAFFINE_TOKEN_PLACEHOLDER',  # Affine DeFi
            'AMBIENT': '0xAMBIENT_TOKEN_PLACEHOLDER', # Ambient Finance
        }

    def _get_zircuit_patterns(self) -> Dict[str, List[str]]:
        """Get Zircuit-specific contract patterns and common function names."""
        return {
            # Zircuit-specific DeFi patterns
            'staking_functions': [
                'stake', 'unstake', 'claim', 'harvest', 'compound',
                'delegate', 'undelegate', 'restake', 'withdraw'
            ],
            'liquid_staking_functions': [
                'deposit', 'requestWithdrawal', 'claimWithdrawal', 
                'mint', 'redeem', 'rebase'
            ],
            'bridge_functions': [
                'bridgeDeposit', 'bridgeWithdraw', 'mint', 'burn', 
                'finalizeBridgeDeposit', 'proveBridgeWithdrawal',
                'addFunds', 'addFundsNative', 'withdrawWithData'
            ],
            'defi_functions': [
                'swap', 'addLiquidity', 'removeLiquidity', 'deposit', 
                'withdraw', 'borrow', 'repay', 'flashLoan'
            ],
            'governance_functions': [
                'propose', 'vote', 'execute', 'delegate', 'undelegate',
                'castVote', 'castVoteWithReason'
            ],
            'erc20_functions': [
                'transfer', 'transferFrom', 'approve', 'allowance', 
                'balanceOf', 'totalSupply', 'decimals', 'symbol', 'name'
            ],
            'erc721_functions': [
                'transferFrom', 'approve', 'setApprovalForAll', 'tokenURI', 
                'ownerOf', 'balanceOf', 'getApproved', 'isApprovedForAll'
            ],
            'security_functions': [
                'pause', 'unpause', 'emergencyWithdraw', 'setOwner', 
                'grantRole', 'revokeRole', 'authorize'
            ],
            'zircuit_specific': [
                'addFunds', 'addFundsNative', 'withdrawWithData',
                'allowDeposits', 'allowDepositsGlobal', 'authorize'
            ]
        }

    async def parse_abi(self, abi_json: str, contract_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse ABI JSON and generate an enhanced LLM-friendly ABI format.
        Optimized for Zircuit smart contracts with enhanced context and examples.
        """
        try:
            # Parse the ABI
            loaded_json = json.loads(abi_json)
            
            # Handle different ABI formats
            if isinstance(loaded_json, dict) and "abi" in loaded_json:
                abi = loaded_json["abi"]
            elif isinstance(loaded_json, list):
                abi = loaded_json
            else:
                logger.error(f'Unexpected ABI format')
                return {'error': 'Invalid ABI format. Expected array or object with "abi" key'}

            # Group ABI items by type
            functions = [item for item in abi if item.get('type') == 'function']
            events = [item for item in abi if item.get('type') == 'event']
            errors = [item for item in abi if item.get('type') == 'error']
            constructors = [item for item in abi if item.get('type') == 'constructor']
            
            # Process functions for enhanced documentation
            function_info = {}
            for func in functions:
                name = func.get('name', '')
                inputs = func.get('inputs', [])
                outputs = func.get('outputs', [])
                state_mutability = func.get('stateMutability', '')
                
                # Enhanced information for better LLM understanding
                enhanced_inputs = []
                for inp in inputs:
                    enhanced_input = {
                        'name': inp.get('name', ''),
                        'type': inp.get('type', ''),
                        'description': self._generate_enhanced_param_description(
                            inp.get('name', ''), inp.get('type', ''), name
                        ),
                        'components': inp.get('components', []) if inp.get('type', '').startswith('tuple') else None,
                        'validation': self._get_parameter_validation(inp.get('name', ''), inp.get('type', ''))
                    }
                    
                    # Add Zircuit-specific context
                    if inp.get('type') == 'address':
                        enhanced_input['common_addresses'] = self._get_relevant_addresses(name)
                        enhanced_input['address_validation'] = "Must be a valid Ethereum address (42 characters, starts with 0x)"
                        enhanced_input['zircuit_context'] = self._get_zircuit_address_context(name, inp.get('name', ''))
                    elif 'amount' in inp.get('name', '').lower() and inp.get('type', '').startswith('uint'):
                        enhanced_input['decimals_info'] = self._get_token_decimals_info()
                        enhanced_input['amount_examples'] = self._get_amount_examples(inp.get('type', ''))
                        enhanced_input['zircuit_token_context'] = self._get_zircuit_token_context()
                    
                    enhanced_inputs.append(enhanced_input)
                
                enhanced_outputs = []
                for out in outputs:
                    enhanced_output = {
                        'name': out.get('name', ''),
                        'type': out.get('type', ''),
                        'description': self._generate_enhanced_output_description(
                            out.get('name', ''), out.get('type', ''), name
                        ),
                        'components': out.get('components', []) if out.get('type', '').startswith('tuple') else None
                    }
                    enhanced_outputs.append(enhanced_output)
                
                # Generate enhanced descriptions and examples
                description = self._generate_enhanced_function_description(name, state_mutability, inputs, outputs)
                example_usage = self._generate_enhanced_example_usage(name, inputs)
                security_level = self._determine_enhanced_security_level(name, state_mutability, inputs)
                gas_estimation = self._estimate_gas_usage(name, state_mutability, inputs)
                
                function_info[name] = {
                    'name': name,
                    'inputs': enhanced_inputs,
                    'outputs': enhanced_outputs,
                    'stateMutability': state_mutability,
                    'description': description,
                    'parameters': enhanced_inputs,  # Adding parameters at top level for easier access
                    'security_level': security_level,
                    'gas_estimation': gas_estimation,
                    'related_functions': self._find_related_functions(name, functions),
                    'example_usage': example_usage,
                    'zircuit_specific': self._get_zircuit_specific_info(name),
                    'prerequisites': self._get_function_prerequisites(name, state_mutability),
                    'common_errors': self._get_common_errors(name),
                    'best_practices': self._get_best_practices(name, state_mutability),
                    'interaction_patterns': self._get_zircuit_interaction_patterns(name),
                    'bridge_context': self._get_bridge_context(name) if self._is_bridge_function(name) else None
                }
            
            # If contract source is provided, use it to enhance the ABI with better descriptions
            if contract_source:
                function_info = await self._enhance_abi_with_source_flattened(function_info, contract_source, events)
                
            # Add contract-level metadata
            contract_metadata = self._analyze_contract_metadata(functions, events, errors)
            
            # Return a comprehensive structure that's easier for LLM agents to use
            return {
                'functions': function_info,
                'contract_metadata': contract_metadata,
                'zircuit_context': self._get_contract_zircuit_context(functions),
                'events': self._process_events(events),
                'errors': self._process_errors(errors),
                'constructors': self._process_constructors(constructors)
            }
            
        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse ABI JSON: {e}')
            return {'error': 'Invalid ABI JSON format'}

    def _generate_enhanced_param_description(self, param_name: str, param_type: str, func_name: str) -> str:
        """Generate enhanced description for a parameter with Zircuit-specific context."""
        # Handle common parameter patterns with Zircuit context
        if param_type == 'address':
            if 'to' in param_name.lower():
                return f"The recipient address for the {func_name} operation on Zircuit. Must be a valid Ethereum address."
            elif 'from' in param_name.lower():
                return f"The sender address for the {func_name} operation. Usually msg.sender on Zircuit."
            elif 'token' in param_name.lower():
                zircuit_tokens = ", ".join(self.zircuit_tokens.keys())
                return f"The contract address of the token to interact with on Zircuit. Common tokens: {zircuit_tokens}. For LST/LRT tokens, check Zircuit's Liquidity Hub."
            elif 'owner' in param_name.lower():
                return f"The owner address for {func_name}. Must have appropriate permissions on Zircuit."
            else:
                return f"An Ethereum address parameter for {func_name}. Must be a valid 42-character address starting with 0x."
        
        elif param_type.startswith('uint'):
            if 'amount' in param_name.lower():
                return f"The amount for {func_name} on Zircuit. Remember to account for token decimals (usually 18 for most tokens, 6 for USDC/USDT). For LST/LRT tokens, amounts may have different decimal precision."
            elif 'id' in param_name.lower():
                return f"A unique identifier (ID) for {func_name}. Must be a positive integer."
            elif 'deadline' in param_name.lower():
                return f"Unix timestamp deadline for {func_name}. Transaction will revert if executed after this time. Consider Zircuit's fast finality when setting deadlines."
            elif 'fee' in param_name.lower():
                return f"Fee amount for {func_name}. Usually specified in basis points (100 = 1%). Zircuit offers near-zero fees compared to Ethereum mainnet."
            else:
                return f"An unsigned integer parameter for {func_name}. Range: 0 to 2^{param_type[4:] if len(param_type) > 4 else '256'}-1."
        
        elif param_type.startswith('int'):
            return f"A signed integer parameter for {func_name}. Can be positive or negative within the range of {param_type}."
        
        elif param_type == 'bool':
            return f"A boolean flag (true/false) that determines the behavior of {func_name}."
        
        elif param_type == 'bytes' or param_type.startswith('bytes'):
            if 'data' in param_name.lower():
                return f"Binary data for {func_name}. This could contain encoded function calls, signatures, or other binary information for Zircuit operations."
            else:
                return f"Binary data parameter for {func_name}. Encoded as hexadecimal string starting with 0x."
        
        elif param_type == 'string':
            return f"A text string parameter for {func_name}. UTF-8 encoded text data."
        
        elif param_type.startswith('tuple'):
            return f"A complex data structure containing multiple fields for {func_name}. Check the components array for field details."
        
        else:
            return f"Parameter of type {param_type} for {func_name}."

    def _generate_enhanced_output_description(self, output_name: str, output_type: str, func_name: str) -> str:
        """Generate enhanced description for function outputs."""
        if output_type == 'bool':
            return f"Returns true if {func_name} operation succeeded, false otherwise."
        elif output_type.startswith('uint'):
            if 'balance' in output_name.lower():
                return f"The balance amount returned by {func_name}. Consider token decimals when displaying."
            elif 'amount' in output_name.lower():
                return f"The amount returned by {func_name}. May need decimal adjustment for display."
            else:
                return f"A numerical value returned by {func_name}."
        elif output_type == 'address':
            return f"An Ethereum address returned by {func_name}."
        else:
            return f"Returns {output_type} from {func_name}."

    def _generate_enhanced_function_description(self, func_name: str, state_mutability: str, 
                                              inputs: List[Dict], outputs: List[Dict]) -> str:
        """Generate enhanced function description with Zircuit context."""
        # Determine function category
        categories = []
        for category, funcs in self.zircuit_patterns.items():
            if any(pattern in func_name.lower() for pattern in funcs):
                categories.append(category.replace('_', ' ').title())
        
        category_text = f" ({', '.join(categories)})" if categories else ""
        
        # Basic description based on state mutability
        if state_mutability == 'view':
            base_desc = f"A read-only function that queries {func_name} data without modifying blockchain state."
        elif state_mutability == 'pure':
            base_desc = f"A pure function that performs {func_name} calculations without reading or modifying state."
        elif state_mutability == 'payable':
            base_desc = f"A payable function that can receive ETH while executing {func_name}."
        else:
            base_desc = f"A state-modifying function that executes {func_name} on the blockchain."
        
        # Add parameter count and complexity info
        param_count = len(inputs)
        if param_count == 0:
            param_text = "Takes no parameters."
        elif param_count == 1:
            param_text = f"Takes 1 parameter: {inputs[0].get('name', 'unnamed')}."
        else:
            param_text = f"Takes {param_count} parameters."
        
        # Add return value info
        return_count = len(outputs)
        if return_count == 0:
            return_text = "Does not return any values."
        elif return_count == 1:
            return_text = f"Returns: {outputs[0].get('name', 'result')}."
        else:
            return_text = f"Returns {return_count} values."
        
        return f"{base_desc}{category_text} {param_text} {return_text}"

    def _generate_enhanced_example_usage(self, func_name: str, inputs: List[Dict]) -> str:
        """Generate enhanced example usage with realistic Zircuit values."""
        if not inputs:
            return f"{func_name}()"
        
        example_params = []
        for inp in inputs:
            param_type = inp.get('type', '')
            param_name = inp.get('name', '')
            
            if param_type == 'address':
                if 'token' in param_name.lower():
                    example_params.append('"0x2b2d59d84f5903de7e370b1c999b358673f2cdde"  // USDC token')
                elif 'to' in param_name.lower():
                    example_params.append('"0x742d35cc6634C0532925a3b8D8c1C41f0BbF7C5C"  // recipient address')
                else:
                    example_params.append('"0x742d35cc6634C0532925a3b8D8c1C41f0BbF7C5C"  // example address')
            elif param_type.startswith('uint'):
                if 'amount' in param_name.lower():
                    if '256' in param_type:
                        example_params.append('"1000000000000000000"  // 1 token (18 decimals)')
                    else:
                        example_params.append('1000000  // 1 USDC (6 decimals)')
                elif 'deadline' in param_name.lower():
                    example_params.append(str(int(1700000000 + 3600)) + '  // 1 hour from now')
                else:
                    example_params.append('100')
            elif param_type == 'bool':
                example_params.append('true')
            elif param_type == 'string':
                example_params.append('"example string"')
            else:
                example_params.append('/* value */')
        
        return f"{func_name}({', '.join(example_params)})"

    def _determine_enhanced_security_level(self, func_name: str, state_mutability: str, inputs: List[Dict]) -> str:
        """Determine security level with enhanced analysis."""
        high_risk_patterns = ['withdraw', 'transfer', 'approve', 'mint', 'burn', 'emergency', 'owner', 'admin']
        medium_risk_patterns = ['deposit', 'stake', 'swap', 'claim']
        
        # Check function name for risk patterns
        name_lower = func_name.lower()
        if any(pattern in name_lower for pattern in high_risk_patterns):
            risk_level = 'high'
        elif any(pattern in name_lower for pattern in medium_risk_patterns):
            risk_level = 'medium'
        elif state_mutability in ['view', 'pure']:
            risk_level = 'low'
        else:
            risk_level = 'medium'
        
        # Increase risk for payable functions
        if state_mutability == 'payable':
            if risk_level == 'low':
                risk_level = 'medium'
            elif risk_level == 'medium':
                risk_level = 'high'
        
        return risk_level

    def _estimate_gas_usage(self, func_name: str, state_mutability: str, inputs: List[Dict]) -> Dict[str, Any]:
        """Estimate gas usage for the function."""
        if state_mutability in ['view', 'pure']:
            return {
                'estimated_gas': 'N/A (read-only)',
                'gas_range': '0',
                'factors': 'No gas cost for read operations'
            }
        
        # Base gas estimates (these are rough estimates)
        base_gas = 21000  # Transaction base cost
        
        # Add complexity based on function patterns
        name_lower = func_name.lower()
        if 'transfer' in name_lower:
            base_gas += 65000
        elif 'approve' in name_lower:
            base_gas += 45000
        elif 'swap' in name_lower:
            base_gas += 150000
        elif 'deposit' in name_lower or 'withdraw' in name_lower:
            base_gas += 100000
        else:
            base_gas += 50000
        
        # Add for each parameter (rough estimate)
        base_gas += len(inputs) * 5000
        
        return {
            'estimated_gas': f"{base_gas:,}",
            'gas_range': f"{int(base_gas * 0.8):,} - {int(base_gas * 1.5):,}",
            'factors': 'Gas cost varies based on network congestion and actual execution path'
        }

    def _find_related_functions(self, func_name: str, all_functions: List[Dict]) -> List[str]:
        """Find functions that are commonly used together."""
        related = []
        name_lower = func_name.lower()
        
        # Common patterns
        if 'approve' in name_lower:
            related.extend([f['name'] for f in all_functions if 'transfer' in f.get('name', '').lower()])
        elif 'transfer' in name_lower:
            related.extend([f['name'] for f in all_functions if 'approve' in f.get('name', '').lower()])
        elif 'deposit' in name_lower:
            related.extend([f['name'] for f in all_functions if 'withdraw' in f.get('name', '').lower()])
        elif 'stake' in name_lower:
            related.extend([f['name'] for f in all_functions if any(x in f.get('name', '').lower() for x in ['unstake', 'claim', 'harvest'])])
        
        return related[:3]  # Limit to top 3 related functions

    def _get_zircuit_specific_info(self, func_name: str) -> Dict[str, Any]:
        """Get Zircuit-specific information for the function."""
        name_lower = func_name.lower()
        info = {
            'is_bridge_function': any(pattern in name_lower for pattern in self.zircuit_patterns['bridge_functions']),
            'is_defi_function': any(pattern in name_lower for pattern in self.zircuit_patterns['defi_functions']),
            'zircuit_documentation': f"https://docs.zircuit.com/contracts/{func_name.lower()}",
            'layer2_considerations': []
        }
        
        if info['is_bridge_function']:
            info['layer2_considerations'].append('This function interacts with Zircuit bridge contracts')
        if 'deposit' in name_lower or 'withdraw' in name_lower:
            info['layer2_considerations'].append('Consider finalization time for L1 <-> L2 transfers')
        
        return info

    def _get_function_prerequisites(self, func_name: str, state_mutability: str) -> List[str]:
        """Get prerequisites for calling this function."""
        prerequisites = []
        name_lower = func_name.lower()
        
        if 'transfer' in name_lower and 'from' in name_lower:
            prerequisites.append('Token approval must be set using approve() function')
        elif 'withdraw' in name_lower:
            prerequisites.append('Must have sufficient balance or stake')
        elif 'claim' in name_lower:
            prerequisites.append('Must have pending rewards to claim')
        elif state_mutability == 'payable':
            prerequisites.append('Can receive ETH - ensure msg.value is set correctly')
        
        if state_mutability not in ['view', 'pure']:
            prerequisites.append('Requires gas for transaction execution')
            prerequisites.append('Account must have sufficient ETH for gas fees')
        
        return prerequisites

    def _get_common_errors(self, func_name: str) -> List[str]:
        """Get common errors that might occur with this function."""
        errors = []
        name_lower = func_name.lower()
        
        if 'transfer' in name_lower:
            errors.extend([
                'ERC20InsufficientBalance: Insufficient token balance',
                'ERC20InsufficientAllowance: Allowance too low for transferFrom'
            ])
        if 'approve' in name_lower:
            errors.append('ERC20InvalidSpender: Cannot approve zero address')
        if 'withdraw' in name_lower:
            errors.append('InsufficientFunds: Not enough balance to withdraw')
        
        # Common errors for all state-changing functions
        if func_name not in ['view', 'pure']:
            errors.extend([
                'OutOfGas: Transaction ran out of gas',
                'RevertedTransaction: Function requirements not met'
            ])
        
        return errors

    def _get_best_practices(self, func_name: str, state_mutability: str) -> List[str]:
        """Get best practices for using this function."""
        practices = []
        name_lower = func_name.lower()
        
        if 'approve' in name_lower:
            practices.extend([
                'Set allowance to 0 before setting new value to prevent race conditions',
                'Use safeApprove pattern for production applications'
            ])
        elif 'transfer' in name_lower:
            practices.extend([
                'Check recipient address is not zero address',
                'Verify token balance before transfer'
            ])
        elif state_mutability == 'payable':
            practices.append('Validate msg.value matches expected ETH amount')
        
        if state_mutability not in ['view', 'pure']:
            practices.extend([
                'Use appropriate gas limit to prevent out-of-gas errors',
                'Implement proper error handling for failed transactions',
                'Consider using multicall for batch operations'
            ])
        
        return practices

    def _get_parameter_validation(self, param_name: str, param_type: str) -> Dict[str, str]:
        """Get validation rules for parameters."""
        validation = {}
        
        if param_type == 'address':
            validation['format'] = 'Must be a valid Ethereum address (0x followed by 40 hex characters)'
            validation['not_zero'] = 'Address should not be 0x0000000000000000000000000000000000000000 unless explicitly allowed'
        elif param_type.startswith('uint'):
            validation['range'] = f'Must be between 0 and 2^{param_type[4:] if len(param_type) > 4 else "256"}-1'
            if 'amount' in param_name.lower():
                validation['decimals'] = 'Consider token decimals when specifying amounts'
        
        return validation

    def _get_relevant_addresses(self, func_name: str) -> Dict[str, str]:
        """Get relevant Zircuit addresses for the function context."""
        relevant = {}
        name_lower = func_name.lower()
        
        if any(keyword in name_lower for keyword in ['token', 'erc20', 'transfer', 'approve']):
            relevant.update(self.zircuit_tokens)
        
        return relevant

    def _get_token_decimals_info(self) -> str:
        """Get information about token decimals on Zircuit."""
        return "Most tokens use 18 decimals (like ETH), but USDC and USDT typically use 6 decimals. Always check token.decimals() before calculations."

    def _get_amount_examples(self, uint_type: str) -> List[str]:
        """Get example amounts for different uint types."""
        if uint_type == 'uint256':
            return [
                "1000000000000000000 (1 token with 18 decimals)",
                "1000000 (1 token with 6 decimals like USDC)",
                "500000000000000000 (0.5 tokens with 18 decimals)"
            ]
        else:
            return ["1000000 (example amount)"]

    def _analyze_contract_metadata(self, functions: List[Dict], events: List[Dict], errors: List[Dict]) -> Dict[str, Any]:
        """Analyze contract to provide metadata about its purpose and type."""
        function_names = [f.get('name', '').lower() for f in functions]
        
        contract_type = []
        if any(name in function_names for name in ['transfer', 'approve', 'balanceof']):
            contract_type.append('ERC20 Token')
        if any(name in function_names for name in ['transferfrom', 'approve', 'tokenuri']):
            contract_type.append('ERC721 NFT')
        if any(name in function_names for name in ['swap', 'addliquidity', 'removeliquidity']):
            contract_type.append('DEX/AMM')
        if any(name in function_names for name in ['deposit', 'withdraw', 'stake']):
            contract_type.append('Staking/Yield')
        if any(name in function_names for name in ['mint', 'burn', 'bridgedeposit']):
            contract_type.append('Bridge')
        
        return {
            'contract_types': contract_type,
            'function_count': len(functions),
            'event_count': len(events),
            'error_count': len(errors),
            'has_payable_functions': any(f.get('stateMutability') == 'payable' for f in functions),
            'complexity_score': self._calculate_complexity_score(functions)
        }

    def _calculate_complexity_score(self, functions: List[Dict]) -> str:
        """Calculate a simple complexity score for the contract."""
        score = len(functions)
        
        # Add complexity for functions with many parameters
        for func in functions:
            inputs = func.get('inputs', [])
            if len(inputs) > 3:
                score += len(inputs) - 3
        
        if score < 10:
            return 'Low'
        elif score < 25:
            return 'Medium'
        else:
            return 'High'

    def _process_events(self, events: List[Dict]) -> Dict[str, Any]:
        """Process contract events with enhanced descriptions."""
        processed_events = {}
        
        for event in events:
            name = event.get('name', '')
            inputs = event.get('inputs', [])
            
            processed_events[name] = {
                'name': name,
                'inputs': inputs,
                'description': f"Event emitted when {name} operation occurs",
                'indexed_count': len([inp for inp in inputs if inp.get('indexed', False)]),
                'monitoring_importance': self._get_event_importance(name)
            }
        
        return processed_events

    def _process_errors(self, errors: List[Dict]) -> Dict[str, Any]:
        """Process contract errors with descriptions."""
        processed_errors = {}
        
        for error in errors:
            name = error.get('name', '')
            inputs = error.get('inputs', [])
            
            processed_errors[name] = {
                'name': name,
                'inputs': inputs,
                'description': f"Error thrown when {name} condition is not met",
                'likely_causes': self._get_error_causes(name)
            }
        
        return processed_errors

    def _process_constructors(self, constructors: List[Dict]) -> List[Dict]:
        """Process constructor information."""
        processed = []
        
        for constructor in constructors:
            inputs = constructor.get('inputs', [])
            processed.append({
                'inputs': inputs,
                'description': 'Contract constructor - called once during deployment',
                'parameter_count': len(inputs)
            })
        
        return processed

    def _get_event_importance(self, event_name: str) -> str:
        """Determine monitoring importance of events."""
        high_importance = ['transfer', 'approval', 'deposit', 'withdraw', 'swap']
        medium_importance = ['mint', 'burn', 'stake', 'claim']
        
        name_lower = event_name.lower()
        if any(pattern in name_lower for pattern in high_importance):
            return 'High'
        elif any(pattern in name_lower for pattern in medium_importance):
            return 'Medium'
        else:
            return 'Low'

    def _get_error_causes(self, error_name: str) -> List[str]:
        """Get likely causes for common errors."""
        name_lower = error_name.lower()
        
        if 'insufficient' in name_lower:
            return ['Not enough balance', 'Allowance too low', 'Insufficient funds']
        elif 'invalid' in name_lower:
            return ['Invalid address provided', 'Invalid parameter value', 'Wrong input format']
        elif 'unauthorized' in name_lower or 'access' in name_lower:
            return ['Caller lacks required permissions', 'Not contract owner', 'Missing role']
        else:
            return ['Check function requirements', 'Verify input parameters', 'Ensure proper contract state']

    async def _enhance_abi_with_source_flattened(self, function_info: Dict[str, Any], 
                                              contract_source: str, 
                                              events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Use LLM to enhance ABI with descriptions from the contract source code, using a flattened format"""
        # Create a format that the prompt expects (functions and events)
        structured_functions = {}
        for func_name, func_data in function_info.items():
            structured_functions[func_name] = {
                'name': func_name,
                'description': func_data.get('description', ''),
                'inputs': func_data.get('inputs', []),
                'outputs': func_data.get('outputs', []),
                'stateMutability': func_data.get('stateMutability', '')
            }
            
        structured_events = {}
        for event in events:
            event_name = event.get('name', '')
            structured_events[event_name] = {
                'name': event_name,
                'inputs': event.get('inputs', []),
                'anonymous': event.get('anonymous', False)
            }
        
        enhancement_prompt = {
            'contract_source': contract_source,
            'functions': json.dumps(structured_functions, indent=2),
            'events': json.dumps(structured_events, indent=2)
        }
        
        enhanced_data = await self.task_processor.run(conversation_round=1, **enhancement_prompt)
        
        try:
            # The new format should already be flattened with function names as top-level keys
            enhanced_result = json.loads(enhanced_data)
            
            # Update our function_info with improved descriptions from the LLM
            for func_name, enhanced_func in enhanced_result.items():
                if func_name in function_info:
                    # Update description
                    if 'description' in enhanced_func:
                        function_info[func_name]['description'] = enhanced_func['description']
                    
                    # Update parameters/inputs descriptions
                    if 'parameters' in enhanced_func:
                        # Match parameters by name or position
                        for i, enhanced_param in enumerate(enhanced_func['parameters']):
                            param_name = enhanced_param.get('name', '')
                            
                            # Try to find by name first
                            found = False
                            for j, existing_param in enumerate(function_info[func_name]['parameters']):
                                if existing_param['name'] == param_name:
                                    if 'description' in enhanced_param:
                                        function_info[func_name]['parameters'][j]['description'] = enhanced_param['description']
                                        # Also update in inputs for consistency
                                        function_info[func_name]['inputs'][j]['description'] = enhanced_param['description']
                                    found = True
                                    break
                            
                            # If not found by name, update by position if possible
                            if not found and i < len(function_info[func_name]['parameters']):
                                if 'description' in enhanced_param:
                                    function_info[func_name]['parameters'][i]['description'] = enhanced_param['description']
                                    function_info[func_name]['inputs'][i]['description'] = enhanced_param['description']
                    
                    # Update security level
                    if 'security_level' in enhanced_func:
                        function_info[func_name]['security_level'] = enhanced_func['security_level']
                    
                    # Update related functions
                    if 'related_functions' in enhanced_func:
                        function_info[func_name]['related_functions'] = enhanced_func['related_functions']
                    
                    # Update example usage
                    if 'example_usage' in enhanced_func:
                        function_info[func_name]['example_usage'] = enhanced_func['example_usage']
            
            return function_info
            
        except json.JSONDecodeError:
            logger.error('Failed to parse enhanced data from LLM')
            return function_info

    def _get_common_tokens(self) -> Dict[str, str]:
        """Return common token addresses on Zircuit."""
        return self.zircuit_tokens

    def _get_zircuit_address_context(self, func_name: str, param_name: str) -> Dict[str, Any]:
        """Get Zircuit-specific context for address parameters."""
        context = {
            'network': 'Zircuit Mainnet',
            'chain_id': 48900,  # Zircuit mainnet chain ID
            'bridge_addresses': {
                'canonical_bridge': '0x_CANONICAL_BRIDGE_ADDRESS',  # To be updated
                'fast_bridge': '0x_FAST_BRIDGE_ADDRESS'  # To be updated
            }
        }
        
        if 'token' in param_name.lower():
            context['token_info'] = {
                'native_eth': '0x0000000000000000000000000000000000000000',
                'popular_tokens': self.zircuit_tokens,
                'liquidity_hub': 'Check Zircuit Liquidity Hub for LST/LRT tokens'
            }
        
        return context

    def _get_zircuit_token_context(self) -> Dict[str, Any]:
        """Get Zircuit-specific token context and information."""
        return {
            'decimals_info': {
                'ETH': 18,
                'most_tokens': 18,
                'USDC': 6,
                'USDT': 6,
                'stablecoins': 'Usually 6 decimals'
            },
            'liquidity_hub_info': 'Zircuit offers a Liquidity Hub for staking ETH and LST/LRT tokens',
            'gas_token': 'ETH (native)',
            'popular_pairs': ['ETH/USDC', 'ETH/stETH', 'ETH/rETH'],
            'bridge_info': 'Tokens can be bridged from Ethereum mainnet via Zircuit bridge'
        }

    def _get_zircuit_interaction_patterns(self, func_name: str) -> List[Dict[str, str]]:
        """Get common interaction patterns for Zircuit functions."""
        patterns = []
        
        # Staking patterns
        if func_name in self.zircuit_patterns['staking_functions']:
            patterns.append({
                'pattern': 'stake_workflow',
                'description': 'Check allowance → approve if needed → stake tokens',
                'sequence': ['allowance', 'approve', func_name]
            })
        
        # Bridge patterns
        if func_name in self.zircuit_patterns['bridge_functions']:
            patterns.append({
                'pattern': 'bridge_workflow',
                'description': 'Deposit from L1 → wait for confirmation → use on L2',
                'sequence': ['bridgeDeposit', 'waitForConfirmation', 'useOnL2']
            })
        
        # DeFi patterns
        if func_name in self.zircuit_patterns['defi_functions']:
            patterns.append({
                'pattern': 'defi_workflow',
                'description': 'Check balances → approve tokens → execute transaction',
                'sequence': ['balanceOf', 'approve', func_name]
            })
        
        return patterns

    def _get_bridge_context(self, func_name: str) -> Optional[Dict[str, Any]]:
        """Get bridge-specific context for bridge functions."""
        if not self._is_bridge_function(func_name):
            return None
        
        return {
            'bridge_type': 'Canonical Bridge' if 'bridge' in func_name.lower() else 'Contract Bridge',
            'confirmation_time': 'Fast finality on Zircuit (~1-2 seconds)',
            'withdrawal_time': 'Standard withdrawal: ~7 days, Fast bridge: minutes',
            'security': 'Protected by Sequencer Level Security (SLS)',
            'fees': 'Near-zero fees on Zircuit',
            'supported_tokens': ['ETH', 'USDC', 'USDT', 'LST/LRT tokens'],
            'bridge_addresses': {
                'canonical': '0x_CANONICAL_BRIDGE_PLACEHOLDER',
                'fast_bridge': '0x_FAST_BRIDGE_PLACEHOLDER'
            }
        }

    def _is_bridge_function(self, func_name: str) -> bool:
        """Check if a function is bridge-related."""
        bridge_keywords = ['bridge', 'deposit', 'withdraw', 'addFunds', 'mint', 'burn']
        return any(keyword in func_name.lower() for keyword in bridge_keywords)

    def _get_contract_zircuit_context(self, functions: List[Dict]) -> Dict[str, Any]:
        """Get overall Zircuit context for the contract."""
        function_names = [f.get('name', '') for f in functions]
        
        contract_type = 'Unknown'
        if any(f in function_names for f in self.zircuit_patterns['bridge_functions']):
            contract_type = 'Bridge Contract'
        elif any(f in function_names for f in self.zircuit_patterns['staking_functions']):
            contract_type = 'Staking Contract'
        elif any(f in function_names for f in self.zircuit_patterns['defi_functions']):
            contract_type = 'DeFi Contract'
        elif any(f in function_names for f in self.zircuit_patterns['erc20_functions']):
            contract_type = 'Token Contract'
        
        return {
            'network': 'Zircuit',
            'contract_type': contract_type,
            'security_features': [
                'Sequencer Level Security (SLS)',
                'AI-powered transaction monitoring',
                'Hybrid ZK-Rollup architecture'
            ],
            'performance': {
                'finality': 'Fast (~1-2 seconds)',
                'fees': 'Near-zero compared to Ethereum',
                'throughput': 'High transaction throughput'
            },
            'ecosystem': {
                'liquidity_hub': 'Available for staking',
                'bridge': 'Canonical bridge to Ethereum',
                'tools': 'Full EVM compatibility with MetaMask, Hardhat, etc.'
            }
        }


async def main():
    input_abi_path = './test_abi/uniswap_v2_abi.json'
    output_function_calling_path = './test_abi/uniswap_v2_function_calling.json'

    with open(input_abi_path, 'r') as input_abi_json:
        test_abi = input_abi_json.read()

    generator = ABIDecoder()
    result = await generator.generate_function_calling(test_abi)

    with open(output_function_calling_path, 'w') as output_function_calling_json:
        json.dump(result, output_function_calling_json, indent=2)


if __name__ == '__main__':
    asyncio.run(main())
