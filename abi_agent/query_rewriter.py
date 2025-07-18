import json
import sys
import re
from typing import List, Dict, Any, Optional

from more_itertools.more import unzip
from jinja2 import Template

from llm_generation.task_processor import TaskProcessor
import asyncio
from loguru import logger
from abi_agent.function_call_generator import FunctionCallGenerator


class QueryRewriter:
    """
    Rewrites user queries to make them more suitable for function calling generation.
    """
    
    def __init__(self, model_name: str = 'o3-mini'):
        """
        Initialize the query rewriter.
        
        Args:
            model_name: The name of the LLM model to use
        """
        self.model_name = model_name
        self.task_processor = TaskProcessor(
            prompt_template_config_path="./prompt_template/rewrite_user_query.yml",
            model_name=model_name
        )

    async def rewrite(self, user_query: str, contract_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Rewrite a user query to make it more suitable for function calling generation.
        
        Args:
            user_query: The original user query
            contract_context: Optional context about the contract (functions, events, etc.)
            
        Returns:
            The rewritten query
        """
        try:
            # Create a context dictionary for the template
            template_context = {
                'user_query': user_query,
                'contract_context': {
                    'contract_id': 'unknown',
                    'address': 'unknown',
                    'functions': {}
                }
            }
            
            # Add contract context if available
            if contract_context:
                # Extract contract information
                if 'contract_id' in contract_context:
                    template_context['contract_context']['contract_id'] = contract_context['contract_id']
                if 'address' in contract_context:
                    template_context['contract_context']['address'] = contract_context['address']
                if 'functions' in contract_context:
                    template_context['contract_context']['functions'] = contract_context['functions']
            
            logger.debug(f"Template context: {template_context}")
            
            # Use the task processor's built-in template rendering
            response = await self.task_processor.run(
                conversation_round=1,
                **template_context
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error rewriting query: {e}")
            logger.error(f"Original query: {user_query}")
            logger.error(f"Contract context: {contract_context}")
            # Fallback to original query if rewriting fails
            return user_query

    async def batch_rewrite(self, queries: List[str], contract_context: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Rewrite multiple queries in parallel.
        
        Args:
            queries: A list of user queries to rewrite
            contract_context: Optional context about the contract
            
        Returns:
            A list of rewritten queries
        """
        # Create a list of tasks for each query
        tasks = [asyncio.create_task(self.rewrite(query, contract_context)) for query in queries]
        # Await all tasks concurrently
        results = await asyncio.gather(*tasks)
        return results


async def process_query(query: str, abi_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Process a user query from start to finish, including rewriting and generating function calls.
    
    Args:
        query: The user query
        abi_path: Optional path to the ABI file
    
    Returns:
        Dict containing the function calls
    """
    # Initialize components
    rewriter = QueryRewriter()
    function_call_generator = FunctionCallGenerator()
    
    # Load ABI if provided
    contract_context = None
    if abi_path:
        with open(abi_path) as f:
            abi_content = f.read()
            abi_data = json.loads(abi_content)
            if 'enhanced_abi' in abi_data:
                contract_context = abi_data['enhanced_abi']
            elif 'functions' in abi_data:
                contract_context = {'functions': abi_data['functions']}
    
    # Rewrite the query
    rewritten_query = await rewriter.rewrite(query, contract_context)
    logger.info(f"Original query: {query}")
    logger.info(f"Rewritten query: {rewritten_query}")
    
    # Generate function calls
    function_calls = await function_call_generator.generate(rewritten_query, abi_path=abi_path)
    
    return {
        'original_query': query,
        'rewritten_query': rewritten_query,
        'function_calls': function_calls
    }


async def main():
    """Example usage of the query rewriter and function call generator."""
    # Sample queries
    simple_queries = [
        "i want to create a uniswap v2 pair for ZRC and ETH",
        "i want to check how many pairs I have created",
        "set the feeto setter as ADDRESS and the feeto as ADDRESS"
    ]

    # Process each query
    results = []
    for query in simple_queries:
        result = await process_query(query)
        results.append(result)
    
    # Display the results
    for result in results:
        logger.info(f"\nUser query: {result['original_query']}")
        logger.info(f"Rewritten query: {result['rewritten_query']}")
        
        if 'function_calling' in result['function_calls']:
            for ind, func_call in enumerate(result['function_calls']['function_calling']):
                function_name = func_call["function_name"]
                parameters = func_call["parameters"]
                pre_condition = func_call["pre_condition"]
                logger.info(f"{ind+1}: {function_name}")
                logger.info(f"Pre-condition: {pre_condition}")
                logger.info(f"Parameters: {parameters}")


if __name__ == '__main__':
    from argparse import ArgumentParser
    
    parser = ArgumentParser(description='Process a user query')
    parser.add_argument('query', nargs='?', help='The user query')
    parser.add_argument('--abi', help='Path to the ABI file')
    parser.add_argument('--batch', action='store_true', help='Run the examples in the main function')
    
    args = parser.parse_args()
    
    if args.batch:
        asyncio.run(main())
    elif args.query:
        result = asyncio.run(process_query(args.query, args.abi))
        print(json.dumps(result, indent=2))
    else:
        print("Please provide a query or use --batch to run the examples")