#!/usr/bin/env python3
"""
Metrics calculation module for Zircuit Agent testing.

This module provides functions to evaluate the performance of the agent
by comparing its output against ground truth test cases.
"""

import json
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from loguru import logger
import difflib


@dataclass
class TestMetrics:
    """Container for test metrics."""
    total_tests: int
    successful_tests: int
    failed_tests: int
    accuracy: float
    function_name_accuracy: float
    parameter_accuracy: float
    value_accuracy: float
    rewritten_query_similarity: float
    contract_selection_accuracy: float
    
    # Detailed breakdown
    function_name_matches: int
    parameter_matches: int
    value_matches: int
    contract_matches: int
    reasoning_quality_score: float


class MetricsCalculator:
    """Calculates various metrics for agent performance evaluation."""
    
    def __init__(self):
        self.similarity_threshold = 0.8
        
    def calculate_string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings using difflib."""
        if not str1 or not str2:
            return 0.0
        
        # Use sequence matcher for similarity
        matcher = difflib.SequenceMatcher(None, str1.lower(), str2.lower())
        return matcher.ratio()
    
    def normalize_parameter_value(self, value: Any) -> str:
        """Normalize parameter values for comparison."""
        if isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return value.lower().strip()
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, list):
            return json.dumps(sorted(value) if all(isinstance(x, str) for x in value) else value)
        elif isinstance(value, dict):
            return json.dumps(value, sort_keys=True)
        else:
            return str(value)
    
    def compare_parameters(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> Tuple[bool, float]:
        """
        Compare function parameters between actual and expected.
        
        Returns:
            Tuple of (exact_match, similarity_score)
        """
        if not actual and not expected:
            return True, 1.0
        
        if not actual or not expected:
            return False, 0.0
        
        # Check if all expected parameters are present
        expected_keys = set(expected.keys())
        actual_keys = set(actual.keys())
        
        # Calculate key similarity
        key_intersection = expected_keys.intersection(actual_keys)
        key_union = expected_keys.union(actual_keys)
        key_similarity = len(key_intersection) / len(key_union) if key_union else 1.0
        
        # Calculate value similarity for matching keys
        value_similarities = []
        exact_matches = 0
        
        for key in key_intersection:
            expected_val = self.normalize_parameter_value(expected[key])
            actual_val = self.normalize_parameter_value(actual[key])
            
            if expected_val == actual_val:
                exact_matches += 1
                value_similarities.append(1.0)
            else:
                # Special handling for addresses and large numbers
                if (key.lower() in ['amount', 'value', '_mintfee'] and 
                    expected_val.isdigit() and actual_val.isdigit()):
                    # For numeric values, check if they're within reasonable range
                    try:
                        exp_num = int(expected_val)
                        act_num = int(actual_val)
                        # Allow 10% deviation for numeric values
                        similarity = max(0, 1 - abs(exp_num - act_num) / max(exp_num, act_num, 1))
                        value_similarities.append(similarity)
                    except ValueError:
                        value_similarities.append(0.0)
                else:
                    # String similarity for other values
                    similarity = self.calculate_string_similarity(expected_val, actual_val)
                    value_similarities.append(similarity)
        
        # Overall parameter similarity
        avg_value_similarity = sum(value_similarities) / len(value_similarities) if value_similarities else 0.0
        overall_similarity = (key_similarity + avg_value_similarity) / 2
        
        # Exact match if all keys and values match
        exact_match = (len(expected_keys) == len(actual_keys) == exact_matches)
        
        return exact_match, overall_similarity
    
    def compare_function_calls(self, actual: List[Dict], expected: List[Dict]) -> Dict[str, Any]:
        """
        Compare actual function calls against expected function calls.
        
        Returns metrics for function call comparison.
        """
        if not actual and not expected:
            return {
                'exact_match': True,
                'function_name_match': True,
                'parameter_match': True,
                'value_match': True,
                'call_count_match': True,
                'similarity_score': 1.0
            }
        
        if not actual or not expected:
            return {
                'exact_match': False,
                'function_name_match': False,
                'parameter_match': False,
                'value_match': False,
                'call_count_match': False,
                'similarity_score': 0.0
            }
        
        # Check call count
        call_count_match = len(actual) == len(expected)
        
        # Compare each function call
        function_matches = []
        parameter_matches = []
        value_matches = []
        
        # Use the minimum count to avoid index errors
        min_calls = min(len(actual), len(expected))
        
        for i in range(min_calls):
            actual_call = actual[i]
            expected_call = expected[i]
            
            # Function name comparison
            actual_func = actual_call.get('function_name', '').lower()
            expected_func = expected_call.get('function_name', '').lower()
            func_match = actual_func == expected_func
            function_matches.append(func_match)
            
            # Parameter comparison
            actual_params = actual_call.get('parameters', {})
            expected_params = expected_call.get('parameters', {})
            param_exact, param_similarity = self.compare_parameters(actual_params, expected_params)
            parameter_matches.append(param_similarity)
            
            # Value comparison (for payable functions)
            actual_value = self.normalize_parameter_value(actual_call.get('value', '0'))
            expected_value = self.normalize_parameter_value(expected_call.get('value', '0'))
            value_match = actual_value == expected_value
            value_matches.append(value_match)
        
        # Calculate overall metrics
        function_name_accuracy = sum(function_matches) / len(function_matches) if function_matches else 0.0
        parameter_accuracy = sum(parameter_matches) / len(parameter_matches) if parameter_matches else 0.0
        value_accuracy = sum(value_matches) / len(value_matches) if value_matches else 0.0
        
        # Overall similarity (weighted average)
        similarity_score = (function_name_accuracy * 0.4 + parameter_accuracy * 0.4 + value_accuracy * 0.2)
        
        # Exact match requires all components to match exactly
        exact_match = (call_count_match and 
                      function_name_accuracy == 1.0 and 
                      all(param >= 0.95 for param in parameter_matches) and
                      value_accuracy == 1.0)
        
        return {
            'exact_match': exact_match,
            'function_name_match': function_name_accuracy == 1.0,
            'parameter_match': parameter_accuracy >= 0.9,
            'value_match': value_accuracy == 1.0,
            'call_count_match': call_count_match,
            'similarity_score': similarity_score,
            'function_name_accuracy': function_name_accuracy,
            'parameter_accuracy': parameter_accuracy,
            'value_accuracy': value_accuracy
        }
    
    def evaluate_test_case(self, actual_result: Dict[str, Any], expected_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a single test case against expected results.
        
        Args:
            actual_result: Result from the agent
            expected_result: Expected ground truth result
            
        Returns:
            Dictionary containing evaluation metrics
        """
        evaluation = {
            'success': actual_result.get('success', False),
            'error': actual_result.get('error'),
            'test_case_id': expected_result.get('test_case_id', 'unknown')
        }
        
        # If the agent failed to process the query, mark as failed
        if not actual_result.get('success', False):
            evaluation.update({
                'overall_match': False,
                'function_calls_match': False,
                'rewritten_query_similarity': 0.0,
                'contract_selection_match': False,
                'function_call_metrics': {
                    'exact_match': False,
                    'similarity_score': 0.0,
                    'function_name_accuracy': 0.0,
                    'parameter_accuracy': 0.0,
                    'value_accuracy': 0.0
                }
            })
            return evaluation
        
        # Compare rewritten query
        actual_query = actual_result.get('rewritten_query', '')
        expected_query = expected_result.get('expected_rewritten_query', '')
        query_similarity = self.calculate_string_similarity(actual_query, expected_query)
        
        # Compare contract selection
        selected_contract = actual_result.get('selected_contract', {}).get('address', '')
        expected_contract = expected_result.get('assumed_contract_address', '')
        contract_match = selected_contract.lower() == expected_contract.lower() if selected_contract and expected_contract else False
        
        # Compare function calls
        actual_calls = actual_result.get('function_calls', {}).get('function_calling', [])
        expected_calls = expected_result.get('ground_truth_function_calls', {}).get('function_calling', [])
        
        function_call_metrics = self.compare_function_calls(actual_calls, expected_calls)
        
        # Overall evaluation
        overall_match = (query_similarity >= 0.7 and 
                        contract_match and 
                        function_call_metrics['exact_match'])
        
        evaluation.update({
            'overall_match': overall_match,
            'function_calls_match': function_call_metrics['exact_match'],
            'rewritten_query_similarity': query_similarity,
            'contract_selection_match': contract_match,
            'function_call_metrics': function_call_metrics
        })
        
        return evaluation
    
    def calculate_aggregate_metrics(self, evaluations: List[Dict[str, Any]]) -> TestMetrics:
        """
        Calculate aggregate metrics from a list of test evaluations.
        
        Args:
            evaluations: List of individual test evaluations
            
        Returns:
            TestMetrics object with aggregate statistics
        """
        total_tests = len(evaluations)
        if total_tests == 0:
            return TestMetrics(
                total_tests=0, successful_tests=0, failed_tests=0,
                accuracy=0.0, function_name_accuracy=0.0, parameter_accuracy=0.0,
                value_accuracy=0.0, rewritten_query_similarity=0.0,
                contract_selection_accuracy=0.0, function_name_matches=0,
                parameter_matches=0, value_matches=0, contract_matches=0,
                reasoning_quality_score=0.0
            )
        
        # Count successes and failures
        successful_tests = sum(1 for eval in evaluations if eval.get('overall_match', False))
        failed_tests = total_tests - successful_tests
        
        # Calculate individual metric averages
        query_similarities = [eval.get('rewritten_query_similarity', 0.0) for eval in evaluations]
        contract_matches = sum(1 for eval in evaluations if eval.get('contract_selection_match', False))
        
        # Function call metrics
        function_name_accuracies = []
        parameter_accuracies = []
        value_accuracies = []
        function_name_matches = 0
        parameter_matches = 0
        value_matches = 0
        
        for eval in evaluations:
            fc_metrics = eval.get('function_call_metrics', {})
            function_name_accuracies.append(fc_metrics.get('function_name_accuracy', 0.0))
            parameter_accuracies.append(fc_metrics.get('parameter_accuracy', 0.0))
            value_accuracies.append(fc_metrics.get('value_accuracy', 0.0))
            
            if fc_metrics.get('function_name_match', False):
                function_name_matches += 1
            if fc_metrics.get('parameter_match', False):
                parameter_matches += 1
            if fc_metrics.get('value_match', False):
                value_matches += 1
        
        # Calculate averages
        accuracy = successful_tests / total_tests
        avg_query_similarity = sum(query_similarities) / len(query_similarities)
        contract_selection_accuracy = contract_matches / total_tests
        avg_function_name_accuracy = sum(function_name_accuracies) / len(function_name_accuracies)
        avg_parameter_accuracy = sum(parameter_accuracies) / len(parameter_accuracies)
        avg_value_accuracy = sum(value_accuracies) / len(value_accuracies)
        
        # Reasoning quality score (based on query similarity and function call accuracy)
        reasoning_quality = (avg_query_similarity + avg_function_name_accuracy + avg_parameter_accuracy) / 3
        
        return TestMetrics(
            total_tests=total_tests,
            successful_tests=successful_tests,
            failed_tests=failed_tests,
            accuracy=accuracy,
            function_name_accuracy=avg_function_name_accuracy,
            parameter_accuracy=avg_parameter_accuracy,
            value_accuracy=avg_value_accuracy,
            rewritten_query_similarity=avg_query_similarity,
            contract_selection_accuracy=contract_selection_accuracy,
            function_name_matches=function_name_matches,
            parameter_matches=parameter_matches,
            value_matches=value_matches,
            contract_matches=contract_matches,
            reasoning_quality_score=reasoning_quality
        )
    
    def generate_detailed_report(self, metrics: TestMetrics, evaluations: List[Dict[str, Any]]) -> str:
        """
        Generate a detailed test report.
        
        Args:
            metrics: Aggregate metrics
            evaluations: Individual test evaluations
            
        Returns:
            Formatted test report string
        """
        report = []
        report.append("=" * 80)
        report.append("ZIRCUIT AGENT TEST REPORT")
        report.append("=" * 80)
        report.append("")
        
        # Summary metrics
        report.append("SUMMARY METRICS:")
        report.append(f"  Total Tests: {metrics.total_tests}")
        report.append(f"  Successful Tests: {metrics.successful_tests}")
        report.append(f"  Failed Tests: {metrics.failed_tests}")
        report.append(f"  Overall Accuracy: {metrics.accuracy:.2%}")
        report.append("")
        
        # Detailed metrics
        report.append("DETAILED METRICS:")
        report.append(f"  Query Rewriting Similarity: {metrics.rewritten_query_similarity:.2%}")
        report.append(f"  Contract Selection Accuracy: {metrics.contract_selection_accuracy:.2%}")
        report.append(f"  Function Name Accuracy: {metrics.function_name_accuracy:.2%}")
        report.append(f"  Parameter Accuracy: {metrics.parameter_accuracy:.2%}")
        report.append(f"  Value Accuracy: {metrics.value_accuracy:.2%}")
        report.append(f"  Reasoning Quality Score: {metrics.reasoning_quality_score:.2%}")
        report.append("")
        
        # Component-wise success counts
        report.append("COMPONENT SUCCESS COUNTS:")
        report.append(f"  Function Name Matches: {metrics.function_name_matches}/{metrics.total_tests}")
        report.append(f"  Parameter Matches: {metrics.parameter_matches}/{metrics.total_tests}")
        report.append(f"  Value Matches: {metrics.value_matches}/{metrics.total_tests}")
        report.append(f"  Contract Matches: {metrics.contract_matches}/{metrics.total_tests}")
        report.append("")
        
        # Failed test cases
        failed_cases = [eval for eval in evaluations if not eval.get('overall_match', False)]
        if failed_cases:
            report.append("FAILED TEST CASES:")
            for i, eval in enumerate(failed_cases, 1):
                test_id = eval.get('test_case_id', 'unknown')
                error = eval.get('error', 'No specific error')
                similarity = eval.get('rewritten_query_similarity', 0.0)
                report.append(f"  {i}. {test_id}")
                report.append(f"     Error: {error}")
                report.append(f"     Query Similarity: {similarity:.2%}")
                report.append(f"     Contract Match: {eval.get('contract_selection_match', False)}")
                report.append(f"     Function Match: {eval.get('function_call_metrics', {}).get('exact_match', False)}")
                report.append("")
        
        # Performance recommendations
        report.append("PERFORMANCE RECOMMENDATIONS:")
        if metrics.accuracy < 0.8:
            report.append("  - Overall accuracy is below 80%. Consider improving query processing.")
        if metrics.function_name_accuracy < 0.9:
            report.append("  - Function name accuracy needs improvement. Review function matching logic.")
        if metrics.parameter_accuracy < 0.8:
            report.append("  - Parameter accuracy is low. Check parameter extraction and normalization.")
        if metrics.contract_selection_accuracy < 0.9:
            report.append("  - Contract selection accuracy needs improvement. Review contract discovery logic.")
        if metrics.rewritten_query_similarity < 0.7:
            report.append("  - Query rewriting similarity is low. Improve query processing prompts.")
        
        if metrics.accuracy >= 0.9:
            report.append("  - Excellent performance! Agent is working well.")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report) 