#!/usr/bin/env python3
"""
Example script to run the Zircuit Agent test framework.

This script demonstrates how to run the testing framework with different configurations.
"""

import asyncio
import sys
from pathlib import Path

# Add the current directory to the path
sys.path.append(str(Path(__file__).parent))

from tests.test_runner import ZircuitAgentTestRunner

async def main():
    print("🔬 Zircuit Agent Test Framework Demo")
    print("=" * 50)
    
    # Initialize the test runner
    runner = ZircuitAgentTestRunner(
        test_cases_file="tests/test_cases.json",
        model_name="o3-mini",  # Change this to your preferred model
        enhanced_abis_dir="data/enhanced_abis",
        contracts_data_path="data/zircuit/zircuit_contract_metadata.json",
        output_dir="tests/results"
    )
    
    # Example 1: Run first 3 test cases with detailed output
    print("\n🚀 Running first 3 test cases...")
    try:
        results = await runner.run_tests(
            max_tests=3,
            save_results=True
        )
        
        if results.get('success'):
            metrics = results['metrics']
            print(f"\n📊 Results:")
            print(f"   Overall Accuracy: {metrics['accuracy']:.1%}")
            print(f"   Function Name Accuracy: {metrics['function_name_accuracy']:.1%}")
            print(f"   Contract Selection Accuracy: {metrics['contract_selection_accuracy']:.1%}")
            print(f"   Files saved to: tests/results/")
        else:
            print(f"❌ Test run failed: {results.get('error')}")
            
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        print(f"💡 This is likely due to missing API credentials.")
        print(f"   Please ensure you have set up your .env file with valid API keys.")

    # Example 2: Show available test cases
    print(f"\n📋 Available test cases:")
    test_cases = runner.load_test_cases()
    for i, tc in enumerate(test_cases[:5], 1):  # Show first 5
        print(f"   {i}. {tc['test_case_id']}: {tc['description']}")
    
    if len(test_cases) > 5:
        print(f"   ... and {len(test_cases) - 5} more test cases")
    
    print(f"\n💡 To run specific tests:")
    print(f"   python tests/test_runner.py --filter 'bridge' --max-tests 5")
    print(f"   python tests/test_runner.py --max-tests 1 --verbose")
    print(f"   python tests/test_runner.py --help")
    
    print(f"\n🧪 To run unit tests:")
    print(f"   python -m pytest tests/test_unit.py -v")

if __name__ == "__main__":
    asyncio.run(main()) 