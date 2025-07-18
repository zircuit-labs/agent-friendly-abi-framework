#!/usr/bin/env python3
"""
Test runner for Zircuit Agent testing framework.

This module provides the main test runner that loads test cases,
executes them against the agent, and generates comprehensive reports.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import asdict
from loguru import logger
import argparse

# Add the parent directory to the path to import the agent
sys.path.append(str(Path(__file__).parent.parent))

from zircuit_agent import ZircuitAgent
from tests.test_metrics import MetricsCalculator, TestMetrics
from tests.mock_data_generator import MockDataGenerator


class ZircuitAgentTestRunner:
    """
    Main test runner for Zircuit Agent testing framework.
    """
    
    def __init__(self, 
                 test_cases_file: str = "tests/test_cases.json",
                 model_name: str = "o3-mini",
                 enhanced_abis_dir: str = "data/enhanced_abis",
                 contracts_data_path: str = "data/zircuit/zircuit_contract_metadata.json",
                 output_dir: str = "tests/results"):
        """
        Initialize the test runner.
        
        Args:
            test_cases_file: Path to the test cases JSON file
            model_name: LLM model to use for testing
            enhanced_abis_dir: Directory containing enhanced ABIs
            contracts_data_path: Path to Zircuit contracts data
            output_dir: Directory to save test results and reports
        """
        self.test_cases_file = Path(test_cases_file)
        self.model_name = model_name
        self.enhanced_abis_dir = Path(enhanced_abis_dir)
        self.contracts_data_path = Path(contracts_data_path)
        self.output_dir = Path(output_dir)
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.agent = ZircuitAgent(
            model_name=model_name,
            contracts_data_path=str(contracts_data_path),
            enhanced_abis_dir=str(enhanced_abis_dir)
        )
        self.metrics_calculator = MetricsCalculator()
        self.mock_data_generator = MockDataGenerator()
        
        # Test execution settings
        self.test_timeout = 30  # seconds per test
        self.max_retries = 2
        
        logger.info(f"Test runner initialized with model: {model_name}")
    
    def load_test_cases(self) -> List[Dict[str, Any]]:
        """
        Load test cases from the JSON file.
        
        Returns:
            List of test case dictionaries
        """
        try:
            with open(self.test_cases_file, 'r', encoding='utf-8') as f:
                test_cases = json.load(f)
            logger.info(f"Loaded {len(test_cases)} test cases from {self.test_cases_file}")
            return test_cases
        except FileNotFoundError:
            logger.error(f"Test cases file not found: {self.test_cases_file}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse test cases JSON: {e}")
            return []
    
    def setup_mock_data(self) -> bool:
        """
        Set up mock enhanced ABIs for testing if real data is not available.
        
        Returns:
            True if setup successful, False otherwise
        """
        try:
            # Check if we have real enhanced ABIs
            if self.enhanced_abis_dir.exists() and list(self.enhanced_abis_dir.glob("*.json")):
                logger.info("Using existing enhanced ABIs for testing")
                return True
            
            # Generate mock data
            logger.info("Generating mock enhanced ABIs for testing...")
            success = self.mock_data_generator.generate_mock_enhanced_abis(str(self.enhanced_abis_dir))
            
            if success:
                logger.info("Mock enhanced ABIs generated successfully")
                return True
            else:
                logger.error("Failed to generate mock enhanced ABIs")
                return False
                
        except Exception as e:
            logger.error(f"Error setting up mock data: {e}")
            return False
    
    async def run_single_test(self, test_case: Dict[str, Any], test_index: int) -> Dict[str, Any]:
        """
        Run a single test case against the agent.
        
        Args:
            test_case: Test case dictionary
            test_index: Index of the test case
            
        Returns:
            Test result dictionary
        """
        test_id = test_case.get('test_case_id', f'test_{test_index}')
        query = test_case.get('natural_language_query', '')
        
        logger.info(f"Running test {test_index + 1}: {test_id}")
        logger.debug(f"Query: {query}")
        
        start_time = time.time()
        
        try:
            # Run the agent with timeout
            result = await asyncio.wait_for(
                self.agent.process_query(query),
                timeout=self.test_timeout
            )
            
            execution_time = time.time() - start_time
            
            # Add test metadata to result
            result['test_case_id'] = test_id
            result['execution_time'] = execution_time
            result['test_index'] = test_index
            
            logger.success(f"Test {test_id} completed in {execution_time:.2f}s")
            return result
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(f"Test {test_id} timed out after {self.test_timeout}s")
            return {
                'test_case_id': test_id,
                'test_index': test_index,
                'success': False,
                'error': f'Test timed out after {self.test_timeout} seconds',
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Test {test_id} failed with error: {e}")
            return {
                'test_case_id': test_id,
                'test_index': test_index,
                'success': False,
                'error': f'Test failed with exception: {str(e)}',
                'execution_time': execution_time
            }
    
    async def run_test_with_retry(self, test_case: Dict[str, Any], test_index: int) -> Dict[str, Any]:
        """
        Run a test case with retry logic.
        
        Args:
            test_case: Test case dictionary
            test_index: Index of the test case
            
        Returns:
            Test result dictionary
        """
        last_result = None
        
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                logger.info(f"Retrying test {test_case.get('test_case_id', test_index)} (attempt {attempt + 1})")
                await asyncio.sleep(1)  # Brief pause between retries
            
            result = await self.run_single_test(test_case, test_index)
            
            # If successful, return immediately
            if result.get('success', False):
                if attempt > 0:
                    result['retry_count'] = attempt
                return result
            
            last_result = result
        
        # All retries failed
        last_result['retry_count'] = self.max_retries
        return last_result
    
    async def run_all_tests(self, 
                          test_filter: Optional[str] = None,
                          max_tests: Optional[int] = None,
                          parallel: bool = False) -> List[Dict[str, Any]]:
        """
        Run all test cases.
        
        Args:
            test_filter: Filter test cases by ID pattern (optional)
            max_tests: Maximum number of tests to run (optional)
            parallel: Whether to run tests in parallel (not recommended for LLM APIs)
            
        Returns:
            List of test results
        """
        test_cases = self.load_test_cases()
        
        if not test_cases:
            logger.error("No test cases loaded")
            return []
        
        # Apply filter if specified
        if test_filter:
            test_cases = [
                tc for tc in test_cases 
                if test_filter.lower() in tc.get('test_case_id', '').lower()
            ]
            logger.info(f"Filtered to {len(test_cases)} test cases matching '{test_filter}'")
        
        # Apply max_tests limit
        if max_tests:
            test_cases = test_cases[:max_tests]
            logger.info(f"Limited to {len(test_cases)} test cases")
        
        if not test_cases:
            logger.warning("No test cases to run after filtering")
            return []
        
        logger.info(f"Running {len(test_cases)} test cases...")
        
        # Setup mock data if needed
        if not self.setup_mock_data():
            logger.error("Failed to setup test data")
            return []
        
        start_time = time.time()
        
        if parallel:
            # Run tests in parallel (use with caution for API rate limits)
            logger.warning("Running tests in parallel - watch for API rate limits")
            semaphore = asyncio.Semaphore(3)  # Limit concurrent tests
            
            async def run_with_semaphore(test_case, index):
                async with semaphore:
                    return await self.run_test_with_retry(test_case, index)
            
            tasks = [run_with_semaphore(tc, i) for i, tc in enumerate(test_cases)]
            results = await asyncio.gather(*tasks)
        else:
            # Run tests sequentially (recommended for LLM APIs)
            results = []
            for i, test_case in enumerate(test_cases):
                result = await self.run_test_with_retry(test_case, i)
                results.append(result)
                
                # Add delay between tests to avoid rate limiting
                if i < len(test_cases) - 1:
                    await asyncio.sleep(0.5)
        
        total_time = time.time() - start_time
        logger.info(f"All tests completed in {total_time:.2f}s")
        
        return results
    
    def evaluate_results(self, 
                        test_results: List[Dict[str, Any]], 
                        test_cases: List[Dict[str, Any]]) -> Tuple[TestMetrics, List[Dict[str, Any]]]:
        """
        Evaluate test results against ground truth.
        
        Args:
            test_results: Results from running tests
            test_cases: Original test cases with ground truth
            
        Returns:
            Tuple of (aggregate metrics, individual evaluations)
        """
        logger.info("Evaluating test results against ground truth...")
        
        # Create a mapping of test_case_id to test case for lookup
        test_case_map = {tc.get('test_case_id', f'test_{i}'): tc for i, tc in enumerate(test_cases)}
        
        evaluations = []
        
        for result in test_results:
            test_id = result.get('test_case_id', 'unknown')
            
            # Find corresponding test case
            test_case = test_case_map.get(test_id)
            if not test_case:
                logger.warning(f"No test case found for result: {test_id}")
                continue
            
            # Evaluate this test case
            evaluation = self.metrics_calculator.evaluate_test_case(result, test_case)
            evaluation['execution_time'] = result.get('execution_time', 0.0)
            evaluation['retry_count'] = result.get('retry_count', 0)
            
            evaluations.append(evaluation)
        
        # Calculate aggregate metrics
        metrics = self.metrics_calculator.calculate_aggregate_metrics(evaluations)
        
        logger.info(f"Evaluation complete. Overall accuracy: {metrics.accuracy:.2%}")
        
        return metrics, evaluations
    
    def save_results(self, 
                    test_results: List[Dict[str, Any]], 
                    metrics: TestMetrics, 
                    evaluations: List[Dict[str, Any]],
                    test_run_id: str) -> Dict[str, str]:
        """
        Save test results, metrics, and reports to files.
        
        Args:
            test_results: Raw test results
            metrics: Aggregate metrics
            evaluations: Individual test evaluations
            test_run_id: Unique identifier for this test run
            
        Returns:
            Dictionary mapping output type to file path
        """
        output_files = {}
        
        # Save raw test results
        results_file = self.output_dir / f"test_results_{test_run_id}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, indent=2, default=str)
        output_files['results'] = str(results_file)
        
        # Save metrics
        metrics_file = self.output_dir / f"test_metrics_{test_run_id}.json"
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(metrics), f, indent=2)
        output_files['metrics'] = str(metrics_file)
        
        # Save evaluations
        eval_file = self.output_dir / f"test_evaluations_{test_run_id}.json"
        with open(eval_file, 'w', encoding='utf-8') as f:
            json.dump(evaluations, f, indent=2, default=str)
        output_files['evaluations'] = str(eval_file)
        
        # Generate and save detailed report
        report = self.metrics_calculator.generate_detailed_report(metrics, evaluations)
        report_file = self.output_dir / f"test_report_{test_run_id}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        output_files['report'] = str(report_file)
        
        # Generate summary report (JSON format for easy parsing)
        summary = {
            'test_run_id': test_run_id,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'model_name': self.model_name,
            'total_tests': metrics.total_tests,
            'successful_tests': metrics.successful_tests,
            'accuracy': metrics.accuracy,
            'function_name_accuracy': metrics.function_name_accuracy,
            'parameter_accuracy': metrics.parameter_accuracy,
            'contract_selection_accuracy': metrics.contract_selection_accuracy,
            'reasoning_quality_score': metrics.reasoning_quality_score,
            'files': output_files
        }
        
        summary_file = self.output_dir / f"test_summary_{test_run_id}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        output_files['summary'] = str(summary_file)
        
        logger.info(f"Test results saved to {self.output_dir}")
        return output_files
    
    async def run_tests(self, 
                       test_filter: Optional[str] = None,
                       max_tests: Optional[int] = None,
                       parallel: bool = False,
                       save_results: bool = True) -> Dict[str, Any]:
        """
        Main method to run the complete test suite.
        
        Args:
            test_filter: Filter test cases by ID pattern
            max_tests: Maximum number of tests to run
            parallel: Whether to run tests in parallel
            save_results: Whether to save results to files
            
        Returns:
            Complete test run results
        """
        test_run_id = f"{int(time.time())}_{self.model_name}"
        
        logger.info(f"Starting test run: {test_run_id}")
        
        # Load test cases for evaluation
        test_cases = self.load_test_cases()
        
        # Apply same filtering as run_all_tests
        if test_filter:
            test_cases = [
                tc for tc in test_cases 
                if test_filter.lower() in tc.get('test_case_id', '').lower()
            ]
        
        if max_tests:
            test_cases = test_cases[:max_tests]
        
        # Run tests
        test_results = await self.run_all_tests(test_filter, max_tests, parallel)
        
        if not test_results:
            logger.error("No test results obtained")
            return {
                'test_run_id': test_run_id,
                'success': False,
                'error': 'No test results obtained'
            }
        
        # Evaluate results
        metrics, evaluations = self.evaluate_results(test_results, test_cases)
        
        # Prepare final results
        final_results = {
            'test_run_id': test_run_id,
            'success': True,
            'metrics': asdict(metrics),
            'test_results': test_results,
            'evaluations': evaluations,
            'model_name': self.model_name,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Save results if requested
        if save_results:
            output_files = self.save_results(test_results, metrics, evaluations, test_run_id)
            final_results['output_files'] = output_files
        
        # Print summary
        self.print_test_summary(metrics)
        
        return final_results
    
    def print_test_summary(self, metrics: TestMetrics):
        """
        Print a summary of test results to console.
        
        Args:
            metrics: Test metrics to summarize
        """
        print("\n" + "=" * 60)
        print("ZIRCUIT AGENT TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {metrics.total_tests}")
        print(f"Successful: {metrics.successful_tests}")
        print(f"Failed: {metrics.failed_tests}")
        print(f"Overall Accuracy: {metrics.accuracy:.1%}")
        print(f"Function Name Accuracy: {metrics.function_name_accuracy:.1%}")
        print(f"Parameter Accuracy: {metrics.parameter_accuracy:.1%}")
        print(f"Contract Selection Accuracy: {metrics.contract_selection_accuracy:.1%}")
        print(f"Reasoning Quality: {metrics.reasoning_quality_score:.1%}")
        print("=" * 60)


async def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(description='Zircuit Agent Test Runner')
    parser.add_argument('--test-cases', type=str, default='tests/test_cases.json',
                       help='Path to test cases JSON file')
    parser.add_argument('--model', type=str, default='o3-mini',
                       help='LLM model to use for testing')
    parser.add_argument('--enhanced-abis-dir', type=str, default='data/enhanced_abis',
                       help='Directory containing enhanced ABIs')
    parser.add_argument('--contracts-file', type=str, 
                       default='data/zircuit/zircuit_contract_metadata.json',
                       help='Path to Zircuit contracts data file')
    parser.add_argument('--output-dir', type=str, default='tests/results',
                       help='Directory to save test results')
    parser.add_argument('--filter', type=str,
                       help='Filter test cases by ID pattern')
    parser.add_argument('--max-tests', type=int,
                       help='Maximum number of tests to run')
    parser.add_argument('--parallel', action='store_true',
                       help='Run tests in parallel (use with caution)')
    parser.add_argument('--no-save', action='store_true',
                       help='Do not save results to files')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logger.remove()
        logger.add(sys.stdout, level="DEBUG")
    
    # Initialize test runner
    runner = ZircuitAgentTestRunner(
        test_cases_file=args.test_cases,
        model_name=args.model,
        enhanced_abis_dir=args.enhanced_abis_dir,
        contracts_data_path=args.contracts_file,
        output_dir=args.output_dir
    )
    
    # Run tests
    try:
        results = await runner.run_tests(
            test_filter=args.filter,
            max_tests=args.max_tests,
            parallel=args.parallel,
            save_results=not args.no_save
        )
        
        if results.get('success'):
            print(f"\n✅ Test run completed successfully!")
            if not args.no_save:
                print(f"📁 Results saved to: {args.output_dir}")
        else:
            print(f"\n❌ Test run failed: {results.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Test run interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test run failed with exception: {e}")
        logger.exception("Test run failed")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main()) 