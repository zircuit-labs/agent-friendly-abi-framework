#!/usr/bin/env python3
"""
Zircuit LLM Agent

This agent supports Zircuit blockchain interactions by:
1. Processing Zircuit smart contracts to generate enhanced ABIs
2. Handling natural language queries to find appropriate function calls
3. Providing intelligent contract interaction assistance

Usage:
    python zircuit_agent.py --mode preprocess  # Process contracts and generate enhanced ABIs
    python zircuit_agent.py --mode query --query "I want to transfer tokens"  # Interactive query mode
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger

from abi_agent.abi_decoder import ABIDecoder
from abi_agent.query_rewriter import QueryRewriter
from abi_agent.function_call_generator import FunctionCallGenerator
from abi_agent.contract_selector import ContractSelector


class ZircuitAgent:
    """
    Main Zircuit LLM Agent class that orchestrates contract processing and query handling.
    """
    
    def __init__(self, 
                 model_name: str = 'o3-mini',
                 contracts_data_path: str = 'data/zircuit/zircuit_contract_metadata.json',
                 enhanced_abis_dir: str = 'data/enhanced_abis',
                 use_two_stage_selection: bool = True):
        """
        Initialize the Zircuit Agent.
        
        Args:
            model_name: LLM model to use for processing
            contracts_data_path: Path to Zircuit contracts JSON file
            enhanced_abis_dir: Directory to save enhanced ABIs
            use_two_stage_selection: Whether to use the new two-stage contract selection
        """
        self.model_name = model_name
        self.contracts_data_path = contracts_data_path
        self.enhanced_abis_dir = Path(enhanced_abis_dir)
        self.use_two_stage_selection = use_two_stage_selection
        
        # Ensure enhanced ABIs directory exists
        self.enhanced_abis_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.abi_decoder = ABIDecoder(model_name=model_name)
        self.query_rewriter = QueryRewriter(model_name=model_name)
        self.function_call_generator = FunctionCallGenerator(model_name=model_name)
        
        # Initialize contract selector for two-stage approach
        if self.use_two_stage_selection:
            self.contract_selector = ContractSelector(model_name=model_name)
        
        # Cache for loaded enhanced ABIs
        self._enhanced_abis_cache: Dict[str, Dict] = {}
        
        logger.info(f"Zircuit Agent initialized with model: {model_name}")
        logger.info(f"Two-stage selection: {'enabled' if use_two_stage_selection else 'disabled'}")

    def load_zircuit_contracts(self) -> List[Dict[str, Any]]:
        """
        Load Zircuit contracts from the JSON file.
        
        Returns:
            List of contract dictionaries
        """
        try:
            with open(self.contracts_data_path, 'r') as f:
                contracts = json.load(f)
            logger.info(f"Loaded {len(contracts)} Zircuit contracts")
            return contracts
        except FileNotFoundError:
            logger.error(f"Contracts file not found: {self.contracts_data_path}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse contracts JSON: {e}")
            return []

    def extract_contract_source(self, contract: Dict[str, Any]) -> Optional[str]:
        """
        Extract contract source code from the jsonInput field.
        
        Args:
            contract: Contract dictionary from Zircuit data
            
        Returns:
            Concatenated source code or None if not found
        """
        try:
            json_input = json.loads(contract.get('jsonInput', '{}'))
            sources = json_input.get('sources', {})
            
            # Concatenate all source files
            source_code = ""
            for file_path, file_data in sources.items():
                if 'content' in file_data:
                    source_code += f"// File: {file_path}\n"
                    source_code += file_data['content'] + "\n\n"
            
            return source_code if source_code else None
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to extract source code: {e}")
            return None

    async def process_contract(self, contract: Dict[str, Any]) -> Optional[str]:
        """
        Process a single contract to generate enhanced ABI.
        
        Args:
            contract: Contract dictionary from Zircuit data
            
        Returns:
            Path to the generated enhanced ABI file or None if failed
        """
        contract_id = contract.get('id', 'unknown')
        contract_address = contract.get('address', 'unknown')
        abi = contract.get('abi', '[]')
        
        logger.info(f"Processing contract {contract_id} at {contract_address}")
        
        # Extract source code
        source_code = self.extract_contract_source(contract)
        
        try:
            # Generate enhanced ABI
            enhanced_abi = await self.abi_decoder.parse_abi(abi, source_code)
            
            if 'error' in enhanced_abi:
                logger.error(f"Failed to process contract {contract_id}: {enhanced_abi['error']}")
                return None
            
            # Create enhanced ABI with metadata
            enhanced_contract = {
                'contract_id': contract_id,
                'contract_address': contract_address,
                'original_abi': json.loads(abi) if isinstance(abi, str) else abi,
                'enhanced_abi': enhanced_abi,
                'source_code_available': source_code is not None,
                'processed_at': str(asyncio.get_event_loop().time()),
                'model_used': self.model_name
            }
            
            # Save enhanced ABI
            filename = f"{contract_id}_{contract_address}.json"
            output_path = self.enhanced_abis_dir / filename
            
            with open(output_path, 'w') as f:
                json.dump(enhanced_contract, f, indent=2)
            
            logger.success(f"Enhanced ABI saved to {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to process contract {contract_id}: {e}")
            return None

    async def preprocess_contracts(self, 
                                 max_contracts: Optional[int] = None,
                                 filter_addresses: Optional[List[str]] = None) -> int:
        """
        Preprocess Zircuit contracts to generate enhanced ABIs.
        
        Args:
            max_contracts: Maximum number of contracts to process (None for all)
            filter_addresses: List of specific contract addresses to process
            
        Returns:
            Number of successfully processed contracts
        """
        contracts = self.load_zircuit_contracts()
        
        if not contracts:
            logger.error("No contracts loaded")
            return 0
        
        # Filter contracts if needed
        if filter_addresses:
            contracts = [c for c in contracts if c.get('address') in filter_addresses]
            logger.info(f"Filtered to {len(contracts)} contracts by address")
        
        if max_contracts:
            contracts = contracts[:max_contracts]
            logger.info(f"Limited to {len(contracts)} contracts")
        
        # Process contracts
        successful_count = 0
        for i, contract in enumerate(contracts, 1):
            logger.info(f"Processing contract {i}/{len(contracts)}")
            
            result = await self.process_contract(contract)
            if result:
                successful_count += 1
            
            # Add small delay to avoid overwhelming the LLM API
            await asyncio.sleep(0.1)
        
        logger.info(f"Successfully processed {successful_count}/{len(contracts)} contracts")
        return successful_count

    def load_enhanced_abis(self) -> Dict[str, Dict]:
        """
        Load all enhanced ABIs from the enhanced_abis directory.
        
        Returns:
            Dictionary mapping contract addresses to enhanced ABIs
        """
        if self._enhanced_abis_cache:
            return self._enhanced_abis_cache
        
        enhanced_abis = {}
        
        for abi_file in self.enhanced_abis_dir.glob("*.json"):
            try:
                with open(abi_file, 'r') as f:
                    abi_data = json.load(f)
                
                contract_address = abi_data.get('contract_address')
                if contract_address:
                    enhanced_abis[contract_address] = abi_data
                    
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load enhanced ABI from {abi_file}: {e}")
        
        self._enhanced_abis_cache = enhanced_abis
        logger.info(f"Loaded {len(enhanced_abis)} enhanced ABIs")
        return enhanced_abis

    def find_relevant_contracts(self, 
                              query: str, 
                              max_contracts: int = 5) -> List[Dict]:
        """
        Find contracts relevant to the user query (legacy method for backward compatibility).
        
        Args:
            query: User's natural language query
            max_contracts: Maximum number of contracts to return
            
        Returns:
            List of relevant contract data with enhanced ABIs
        """
        enhanced_abis = self.load_enhanced_abis()
        
        if not enhanced_abis:
            logger.warning("No enhanced ABIs available")
            return []
        
        # Enhanced keyword matching with semantic understanding
        query_lower = query.lower()
        relevant_contracts = []
        
        # Extract key intent and action words from query
        action_keywords = {
            'add': ['add', 'new', 'create'],
            'remove': ['remove', 'delete', 'drop'],
            'swap': ['swap', 'replace', 'change', 'update'],
            'owner': ['owner', 'owners', 'ownership'],
            'threshold': ['threshold', 'limit', 'confirm', 'confirmation'],
            'transfer': ['transfer', 'send', 'move'],
            'approve': ['approve', 'allow', 'permit'],
            'execute': ['execute', 'run', 'call']
        }
        
        for address, contract_data in enhanced_abis.items():
            enhanced_abi = contract_data.get('enhanced_abi', {})
            score = 0
            matched_functions = []
            
            # Check if contract has functions structure
            functions = enhanced_abi.get('functions', {})
            if not functions:
                continue
            
            # Look for exact function name matches and semantic matches
            for func_name, func_data in functions.items():
                if not isinstance(func_data, dict):
                    continue
                
                func_name_lower = func_name.lower()
                description = func_data.get('description', '').lower()
                
                # High score for exact function name relevance
                if 'addowner' in func_name_lower and any(word in query_lower for word in ['add', 'new', 'owner']):
                    score += 10
                    matched_functions.append(func_name)
                elif 'removeowner' in func_name_lower and any(word in query_lower for word in ['remove', 'delete', 'owner']):
                    score += 10
                    matched_functions.append(func_name)
                elif 'swapowner' in func_name_lower and any(word in query_lower for word in ['swap', 'replace', 'change', 'owner']):
                    score += 10
                    matched_functions.append(func_name)
                elif 'threshold' in func_name_lower and 'threshold' in query_lower:
                    score += 8
                    matched_functions.append(func_name)
                
                # Medium score for semantic matches
                for action, keywords in action_keywords.items():
                    if action in query_lower:
                        if any(keyword in func_name_lower for keyword in keywords):
                            score += 5
                            matched_functions.append(func_name)
                        if any(keyword in description for keyword in keywords):
                            score += 3
                
                # Lower score for general keyword matches
                query_words = query_lower.split()
                for word in query_words:
                    if len(word) > 3:  # Ignore short words
                        if word in func_name_lower:
                            score += 2
                        if word in description:
                            score += 1
            
            # Bonus for contracts with multiple relevant functions
            if len(matched_functions) > 1:
                score += 3
            
            # Penalty for contracts with very few functions (likely not what we want)
            if len(functions) < 3:
                score -= 2
            
            if score > 0:
                relevant_contracts.append({
                    'address': address,
                    'score': score,
                    'contract_data': contract_data,
                    'matched_functions': matched_functions
                })
        
        # Sort by relevance score and return top results
        relevant_contracts.sort(key=lambda x: x['score'], reverse=True)
        
        # Log the top matches for debugging
        for i, rc in enumerate(relevant_contracts[:3]):
            logger.info(f"Contract {i+1}: {rc['address'][:10]}... (score: {rc['score']}, functions: {rc['matched_functions'][:3]})")
        
        return relevant_contracts[:max_contracts]

    async def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        Process a user query to generate function calling sequences using two-stage approach.
        
        Args:
            user_query: Natural language query from the user
            
        Returns:
            Dictionary containing the processing results
        """
        logger.info(f"Processing query: {user_query}")
        
        enhanced_abis = self.load_enhanced_abis()
        if not enhanced_abis:
            return {
                'error': 'No enhanced ABIs available. Please run preprocessing first.',
                'query': user_query,
                'relevant_contracts': []
            }
        
        try:
            if self.use_two_stage_selection:
                # Two-stage approach: First select relevant contracts, then generate function calls
                logger.info("Using two-stage contract selection approach")
                
                # Stage 1: Select relevant contracts using simplified ABIs
                selected_contract_addresses = await self.contract_selector.select_contracts(
                    user_query, enhanced_abis, max_contracts=3
                )
                
                if not selected_contract_addresses:
                    return {
                        'error': 'No relevant contracts found for the query',
                        'query': user_query,
                        'relevant_contracts': []
                    }
                
                logger.info(f"Selected contracts: {selected_contract_addresses}")
                
                # Rewrite the query for better context understanding
                # Use the first selected contract for context (could be improved)
                best_contract = enhanced_abis[selected_contract_addresses[0]]
                contract_context = {
                    'functions': best_contract.get('enhanced_abi', {}),
                    'address': best_contract.get('contract_address'),
                    'contract_id': best_contract.get('contract_id')
                }
                
                rewritten_query = await self.query_rewriter.rewrite(user_query, contract_context)
                logger.info(f"Rewritten query: {rewritten_query}")
                
                # Stage 2: Generate function calls from selected contracts
                function_calls = await self.function_call_generator.generate_from_multiple_contracts(
                    rewritten_query,  # Use rewritten query for better specificity
                    enhanced_abis,
                    selected_contract_addresses
                )
                
                return {
                    'original_query': user_query,
                    'rewritten_query': rewritten_query,
                    'selection_method': 'two_stage',
                    'relevant_contracts': [
                        {
                            'address': addr,
                            'contract_id': enhanced_abis.get(addr, {}).get('contract_id', 'unknown')
                        } for addr in selected_contract_addresses
                    ],
                    'selected_contracts': selected_contract_addresses,
                    'function_calls': function_calls,
                    'success': True
                }
                
            else:
                # Legacy single-stage approach for backward compatibility
                logger.info("Using legacy single-stage contract selection approach")
                
                # Find relevant contracts using legacy method
                relevant_contracts = self.find_relevant_contracts(user_query)
                
                if not relevant_contracts:
                    return {
                        'error': 'No relevant contracts found for the query',
                        'query': user_query,
                        'relevant_contracts': []
                    }
                
                # Use the most relevant contract for processing
                best_contract = relevant_contracts[0]['contract_data']
                contract_context = {
                    'functions': best_contract.get('enhanced_abi', {}),
                    'address': best_contract.get('contract_address'),
                    'contract_id': best_contract.get('contract_id')
                }
                
                # Rewrite the query for better context understanding
                rewritten_query = await self.query_rewriter.rewrite(user_query, contract_context)
                logger.info(f"Rewritten query: {rewritten_query}")
                
                # Generate function calls using the legacy single-contract method
                abi_content = json.dumps(best_contract.get('enhanced_abi', {}), indent=2)
                function_calls = await self.function_call_generator.generate(
                    rewritten_query,  # Use rewritten query for better specificity
                    abi_content
                )
                
                return {
                    'original_query': user_query,
                    'rewritten_query': rewritten_query,
                    'selection_method': 'legacy',
                    'relevant_contracts': [
                        {
                            'address': rc['address'],
                            'score': rc['score'],
                            'contract_id': rc['contract_data'].get('contract_id')
                        } for rc in relevant_contracts
                    ],
                    'selected_contract': {
                        'address': contract_context['address'],
                        'contract_id': contract_context['contract_id']
                    },
                    'function_calls': function_calls,
                    'success': True
                }
            
        except Exception as e:
            logger.error(f"Failed to process query: {e}")
            return {
                'error': f'Failed to process query: {str(e)}',
                'query': user_query,
                'selection_method': 'two_stage' if self.use_two_stage_selection else 'legacy'
            }

    async def interactive_mode(self):
        """
        Run the agent in interactive mode for testing queries.
        """
        print("🔗 Zircuit LLM Agent - Interactive Mode")
        print(f"🔧 Two-stage selection: {'enabled' if self.use_two_stage_selection else 'disabled'}")
        print("Type 'quit' to exit, 'reload' to reload enhanced ABIs, 'toggle' to switch selection mode")
        print("-" * 70)
        
        while True:
            try:
                query = input("\n💬 Enter your query: ").strip()
                
                if query.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                elif query.lower() == 'reload':
                    self._enhanced_abis_cache.clear()
                    self.load_enhanced_abis()
                    print("♻️  Enhanced ABIs reloaded")
                    continue
                elif query.lower() == 'toggle':
                    self.use_two_stage_selection = not self.use_two_stage_selection
                    if self.use_two_stage_selection and not hasattr(self, 'contract_selector'):
                        self.contract_selector = ContractSelector(model_name=self.model_name)
                    print(f"🔄 Two-stage selection: {'enabled' if self.use_two_stage_selection else 'disabled'}")
                    continue
                elif not query:
                    continue
                
                print("🔄 Processing query...")
                result = await self.process_query(query)
                
                if result.get('success'):
                    print(f"✅ Query processed successfully!")
                    print(f"📝 Rewritten query: {result['rewritten_query']}")
                    print(f"🔧 Selection method: {result['selection_method']}")
                    
                    if result['selection_method'] == 'two_stage':
                        print(f"🏠 Selected contracts ({len(result['selected_contracts'])}): {result['selected_contracts']}")
                    else:
                        print(f"🏠 Selected contract: {result['selected_contract']['address']}")
                    
                    if 'function_calling' in result.get('function_calls', {}):
                        print("🔧 Function calls:")
                        for i, call in enumerate(result['function_calls']['function_calling'], 1):
                            print(f"  {i}. {call['function_name']}({', '.join(map(str, call['parameters']))})")
                            print(f"     💡 {call.get('reasoning', 'No reasoning provided')}")
                    else:
                        print("⚠️  No function calls generated")
                else:
                    print(f"❌ Error: {result.get('error', 'Unknown error')}")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")


async def main():
    parser = argparse.ArgumentParser(description='Zircuit LLM Agent')
    parser.add_argument('--mode', choices=['preprocess', 'query', 'interactive'], 
                       default='interactive', help='Agent operation mode')
    parser.add_argument('--query', type=str, help='Query to process (for query mode)')
    parser.add_argument('--model', type=str, default='o3-mini', help='LLM model to use')
    parser.add_argument('--max-contracts', type=int, help='Maximum contracts to process')
    parser.add_argument('--contracts-file', type=str, 
                       default='data/zircuit/zircuit_contract_metadata.json',
                       help='Path to Zircuit contracts JSON file')
    parser.add_argument('--enhanced-abis-dir', type=str, default='data/enhanced_abis',
                       help='Directory for enhanced ABIs')
    parser.add_argument('--disable-two-stage', action='store_true',
                       help='Disable two-stage contract selection (use legacy method)')
    
    args = parser.parse_args()
    
    # Initialize agent
    agent = ZircuitAgent(
        model_name=args.model,
        contracts_data_path=args.contracts_file,
        enhanced_abis_dir=args.enhanced_abis_dir,
        use_two_stage_selection=not args.disable_two_stage
    )
    
    if args.mode == 'preprocess':
        print("🚀 Starting contract preprocessing...")
        count = await agent.preprocess_contracts(max_contracts=args.max_contracts)
        print(f"✅ Preprocessing complete! Processed {count} contracts.")
        
    elif args.mode == 'query':
        if not args.query:
            print("❌ Error: --query is required for query mode")
            return
        
        print(f"🔄 Processing query: {args.query}")
        result = await agent.process_query(args.query)
        print(json.dumps(result, indent=2))
        
    elif args.mode == 'interactive':
        await agent.interactive_mode()


if __name__ == '__main__':
    asyncio.run(main()) 