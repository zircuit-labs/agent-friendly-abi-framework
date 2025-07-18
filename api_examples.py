#!/usr/bin/env python3
"""
Example usage of the Zircuit Smart Contract LLM Agent API

This file contains examples of how to interact with the FastAPI endpoints
using Python requests or httpx for async operations.
"""

import asyncio
import json
import requests
import httpx
from typing import Dict, List, Any


class ZircuitAPIClient:
    """
    Client for interacting with the Zircuit Smart Contract LLM Agent API
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        
    def health_check(self) -> Dict[str, Any]:
        """Check API health status"""
        response = requests.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def list_contracts(self) -> Dict[str, Any]:
        """List all available contracts"""
        response = requests.get(f"{self.base_url}/contracts")
        response.raise_for_status()
        return response.json()
    
    def preprocess_contracts(self, 
                           max_contracts: int = None,
                           filter_addresses: List[str] = None,
                           model_name: str = "o3-mini") -> Dict[str, Any]:
        """Preprocess contracts to generate enhanced ABIs"""
        data = {"model_name": model_name}
        if max_contracts:
            data["max_contracts"] = max_contracts
        if filter_addresses:
            data["filter_addresses"] = filter_addresses
            
        response = requests.post(f"{self.base_url}/preprocess", json=data)
        response.raise_for_status()
        return response.json()
    
    def process_query(self, 
                     query: str,
                     max_contracts: int = 3,
                     use_two_stage: bool = True) -> Dict[str, Any]:
        """Process a natural language query"""
        data = {
            "query": query,
            "max_contracts": max_contracts,
            "use_two_stage": use_two_stage
        }
        response = requests.post(f"{self.base_url}/query", json=data)
        response.raise_for_status()
        return response.json()
    
    def select_contracts(self, 
                        query: str,
                        max_contracts: int = 3) -> Dict[str, Any]:
        """Stage 1: Select relevant contracts"""
        data = {
            "query": query,
            "max_contracts": max_contracts
        }
        response = requests.post(f"{self.base_url}/contracts/select", json=data)
        response.raise_for_status()
        return response.json()
    
    def generate_functions(self, 
                          query: str,
                          selected_contracts: List[str]) -> Dict[str, Any]:
        """Stage 2: Generate function calls from selected contracts"""
        data = {
            "query": query,
            "selected_contracts": selected_contracts
        }
        response = requests.post(f"{self.base_url}/functions/generate", json=data)
        response.raise_for_status()
        return response.json()
    
    def rewrite_query(self, 
                     query: str,
                     contract_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Rewrite a natural language query"""
        data = {"query": query}
        if contract_context:
            data["contract_context"] = contract_context
        response = requests.post(f"{self.base_url}/query/rewrite", json=data)
        response.raise_for_status()
        return response.json()
    
    def preprocess_specific_contracts(self,
                                    contract_addresses: List[str],
                                    model_name: str = "o3-mini",
                                    force_reprocess: bool = False) -> Dict[str, Any]:
        """Preprocess specific contracts by their addresses"""
        data = {
            "contract_addresses": contract_addresses,
            "model_name": model_name,
            "force_reprocess": force_reprocess
        }
        response = requests.post(f"{self.base_url}/contracts/preprocess", json=data)
        response.raise_for_status()
        return response.json()


class AsyncZircuitAPIClient:
    """
    Async client for interacting with the Zircuit Smart Contract LLM Agent API
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        
    async def health_check(self) -> Dict[str, Any]:
        """Check API health status"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
    
    async def list_contracts(self) -> Dict[str, Any]:
        """List all available contracts"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/contracts")
            response.raise_for_status()
            return response.json()
    
    async def process_query(self, 
                           query: str,
                           max_contracts: int = 3,
                           use_two_stage: bool = True) -> Dict[str, Any]:
        """Process a natural language query"""
        data = {
            "query": query,
            "max_contracts": max_contracts,
            "use_two_stage": use_two_stage
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/query", json=data)
            response.raise_for_status()
            return response.json()
    
    async def rewrite_query(self, 
                           query: str,
                           contract_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Rewrite a natural language query"""
        data = {"query": query}
        if contract_context:
            data["contract_context"] = contract_context
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}/query/rewrite", json=data)
            response.raise_for_status()
            return response.json()
    
    async def two_stage_workflow(self, query: str, max_contracts: int = 3) -> Dict[str, Any]:
        """Execute complete two-stage workflow"""
        async with httpx.AsyncClient() as client:
            # Stage 1: Contract Selection
            selection_data = {
                "query": query,
                "max_contracts": max_contracts
            }
            selection_response = await client.post(
                f"{self.base_url}/contracts/select", 
                json=selection_data
            )
            selection_response.raise_for_status()
            selection_result = selection_response.json()
            
            if not selection_result["success"]:
                return {"error": "Contract selection failed", "details": selection_result}
            
            selected_contracts = selection_result["selected_contracts"]
            
            # Stage 2: Function Generation
            generation_data = {
                "query": query,
                "selected_contracts": selected_contracts
            }
            generation_response = await client.post(
                f"{self.base_url}/functions/generate",
                json=generation_data
            )
            generation_response.raise_for_status()
            generation_result = generation_response.json()
            
            return {
                "query": query,
                "stage1_result": selection_result,
                "stage2_result": generation_result,
                "selected_contracts": selected_contracts,
                "function_calls": generation_result.get("function_calls"),
                "total_processing_time": (
                    selection_result.get("processing_time", 0) + 
                    generation_result.get("processing_time", 0)
                )
            }


def example_sync_usage():
    """Example synchronous API usage"""
    client = ZircuitAPIClient()
    
    print("=== Zircuit API Client Examples ===\n")
    
    # Health check
    print("1. Health Check:")
    try:
        health = client.health_check()
        print(f"   Status: {health['status']}")
        print(f"   Enhanced ABIs: {health['enhanced_abis_count']}")
        print(f"   Timestamp: {health['timestamp']}\n")
    except Exception as e:
        print(f"   Error: {e}\n")
    
    # List contracts
    print("2. List Contracts:")
    try:
        contracts = client.list_contracts()
        print(f"   Total contracts: {contracts['total_count']}")
        if contracts['contracts']:
            first_contract = contracts['contracts'][0]
            print(f"   First contract: {first_contract['contract_id']} at {first_contract['address']}")
        print()
    except Exception as e:
        print(f"   Error: {e}\n")
    
    # Process query
    print("3. Process Query:")
    try:
        query = "I want to add a new owner to the multisig wallet"
        result = client.process_query(query)
        print(f"   Query: {query}")
        print(f"   Success: {result['success']}")
        print(f"   Selection method: {result['selection_method']}")
        if result['function_calls']:
            calls = result['function_calls'].get('function_calling', [])
            print(f"   Generated {len(calls)} function calls")
        print(f"   Processing time: {result.get('processing_time', 0):.2f}s")
        print()
    except Exception as e:
        print(f"   Error: {e}\n")
    
    # Query rewriting
    print("4. Query Rewriting:")
    try:
        query = "add owner to multisig"
        result = client.rewrite_query(query)
        print(f"   Original: {result['original_query']}")
        print(f"   Rewritten: {result['rewritten_query']}")
        print(f"   Processing time: {result.get('processing_time', 0):.2f}s")
        print()
    except Exception as e:
        print(f"   Error: {e}\n")
    
    # Specific contract preprocessing (example with dummy addresses)
    print("5. Specific Contract Preprocessing:")
    try:
        # Use dummy addresses for demonstration
        addresses = ["0x1234567890123456789012345678901234567890"]
        result = client.preprocess_specific_contracts(addresses, force_reprocess=False)
        print(f"   Requested addresses: {len(addresses)}")
        print(f"   Success: {result['success']}")
        print(f"   Message: {result['message']}")
        print(f"   Processed: {len(result['processed_contracts'])}")
        print(f"   Failed: {len(result['failed_contracts'])}")
        print(f"   Processing time: {result.get('processing_time', 0):.2f}s")
        print()
    except Exception as e:
        print(f"   Error: {e}\n")


async def example_async_usage():
    """Example asynchronous API usage with two-stage workflow"""
    client = AsyncZircuitAPIClient()
    
    print("=== Async Two-Stage Workflow Example ===\n")
    
    try:
        query = "Transfer tokens to another address"
        result = await client.two_stage_workflow(query)
        
        print(f"Query: {query}")
        print(f"Selected contracts: {result['selected_contracts']}")
        print(f"Total processing time: {result['total_processing_time']:.2f}s")
        
        # Stage 1 results
        stage1 = result['stage1_result']
        print(f"\nStage 1 (Contract Selection):")
        print(f"  Success: {stage1['success']}")
        print(f"  Processing time: {stage1.get('processing_time', 0):.2f}s")
        
        # Stage 2 results
        stage2 = result['stage2_result']
        print(f"\nStage 2 (Function Generation):")
        print(f"  Success: {stage2['success']}")
        print(f"  Processing time: {stage2.get('processing_time', 0):.2f}s")
        
        if result['function_calls']:
            calls = result['function_calls'].get('function_calling', [])
            print(f"  Generated {len(calls)} function calls")
            for i, call in enumerate(calls):
                print(f"    {i+1}. {call.get('function_name', 'unknown')}()")
        
    except Exception as e:
        print(f"Error: {e}")


def example_curl_commands():
    """Print example curl commands for API testing"""
    print("=== Example CURL Commands ===\n")
    
    commands = [
        {
            "description": "Health Check",
            "command": "curl -X GET http://localhost:8000/health"
        },
        {
            "description": "List Contracts",
            "command": "curl -X GET http://localhost:8000/contracts"
        },
        {
            "description": "Process Query",
            "command": '''curl -X POST http://localhost:8000/query \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "I want to add a new owner to the multisig",
    "max_contracts": 3,
    "use_two_stage": true
  }' '''
        },
        {
            "description": "Contract Selection (Stage 1)",
            "command": '''curl -X POST http://localhost:8000/contracts/select \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "Transfer ERC20 tokens",
    "max_contracts": 3
  }' '''
        },
        {
            "description": "Function Generation (Stage 2)",
            "command": '''curl -X POST http://localhost:8000/functions/generate \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "Transfer ERC20 tokens",
    "selected_contracts": ["0x1234...", "0x5678..."]
  }' '''
        },
        {
            "description": "Query Rewriting",
            "command": '''curl -X POST http://localhost:8000/query/rewrite \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "add owner to multisig"
  }' '''
        },
        {
            "description": "Specific Contract Preprocessing",
            "command": '''curl -X POST http://localhost:8000/contracts/preprocess \\
  -H "Content-Type: application/json" \\
  -d '{
    "contract_addresses": ["0x1234...", "0x5678..."],
    "model_name": "o3-mini",
    "force_reprocess": false
  }' '''
        }
    ]
    
    for cmd in commands:
        print(f"{cmd['description']}:")
        print(f"{cmd['command']}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Zircuit API Examples")
    parser.add_argument("--mode", choices=["sync", "async", "curl"], 
                       default="sync", help="Example mode to run")
    parser.add_argument("--base-url", default="http://localhost:8000",
                       help="API base URL")
    
    args = parser.parse_args()
    
    if args.mode == "sync":
        example_sync_usage()
    elif args.mode == "async":
        asyncio.run(example_async_usage())
    elif args.mode == "curl":
        example_curl_commands() 