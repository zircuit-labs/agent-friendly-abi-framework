#!/usr/bin/env python3
"""
Unit tests for Zircuit Agent testing framework components.
"""

import pytest
import json
from tests.test_metrics import MetricsCalculator, TestMetrics


class TestMetricsCalculator:
    """Test cases for the MetricsCalculator class."""
    
    def test_string_similarity_exact_match(self):
        """Test string similarity calculation for exact matches."""
        calculator = MetricsCalculator()
        
        similarity = calculator.calculate_string_similarity("hello world", "hello world")
        assert similarity == 1.0
        
        similarity = calculator.calculate_string_similarity("Test String", "test string")
        assert similarity == 1.0  # Case insensitive
    
    def test_string_similarity_partial_match(self):
        """Test string similarity calculation for partial matches."""
        calculator = MetricsCalculator()
        
        similarity = calculator.calculate_string_similarity("hello world", "hello universe")
        assert 0.0 < similarity < 1.0
        
        similarity = calculator.calculate_string_similarity("", "test")
        assert similarity == 0.0
        
        similarity = calculator.calculate_string_similarity("test", "")
        assert similarity == 0.0
    
    def test_normalize_parameter_value(self):
        """Test parameter value normalization."""
        calculator = MetricsCalculator()
        
        # Test different types
        assert calculator.normalize_parameter_value(123) == "123"
        assert calculator.normalize_parameter_value("Test") == "test"
        assert calculator.normalize_parameter_value(True) == "true"
        assert calculator.normalize_parameter_value(False) == "false"
        
        # Test list and dict
        test_list = ["b", "a", "c"]
        normalized_list = calculator.normalize_parameter_value(test_list)
        assert "a" in normalized_list
        
        test_dict = {"key": "value", "another": "test"}
        normalized_dict = calculator.normalize_parameter_value(test_dict)
        assert "key" in normalized_dict
    
    def test_compare_parameters_exact_match(self):
        """Test parameter comparison for exact matches."""
        calculator = MetricsCalculator()
        
        params1 = {"token": "0xTokenAddress", "amount": "150000000000000000000"}
        params2 = {"token": "0xTokenAddress", "amount": "150000000000000000000"}
        
        exact_match, similarity = calculator.compare_parameters(params1, params2)
        assert exact_match == True
        assert similarity == 1.0
    
    def test_compare_parameters_partial_match(self):
        """Test parameter comparison for partial matches."""
        calculator = MetricsCalculator()
        
        params1 = {"token": "0xTokenAddress", "amount": "150000000000000000000"}
        params2 = {"token": "0xTokenAddress", "amount": "140000000000000000000"}  # Different amount
        
        exact_match, similarity = calculator.compare_parameters(params1, params2)
        assert exact_match == False
        assert 0.0 < similarity < 1.0
    
    def test_compare_parameters_empty(self):
        """Test parameter comparison for empty parameters."""
        calculator = MetricsCalculator()
        
        exact_match, similarity = calculator.compare_parameters({}, {})
        assert exact_match == True
        assert similarity == 1.0
        
        exact_match, similarity = calculator.compare_parameters({"key": "value"}, {})
        assert exact_match == False
        assert similarity == 0.0
    
    def test_compare_function_calls_exact_match(self):
        """Test function call comparison for exact matches."""
        calculator = MetricsCalculator()
        
        calls1 = [
            {
                "function_name": "deposit",
                "parameters": {"token": "0xToken", "amount": "150000000000000000000"},
                "value": "0"
            }
        ]
        
        calls2 = [
            {
                "function_name": "deposit",
                "parameters": {"token": "0xToken", "amount": "150000000000000000000"},
                "value": "0"
            }
        ]
        
        result = calculator.compare_function_calls(calls1, calls2)
        assert result['exact_match'] == True
        assert result['similarity_score'] == 1.0
    
    def test_compare_function_calls_different_function(self):
        """Test function call comparison for different functions."""
        calculator = MetricsCalculator()
        
        calls1 = [{"function_name": "deposit", "parameters": {}, "value": "0"}]
        calls2 = [{"function_name": "withdraw", "parameters": {}, "value": "0"}]
        
        result = calculator.compare_function_calls(calls1, calls2)
        assert result['exact_match'] == False
        assert result['function_name_match'] == False
        assert result['similarity_score'] < 1.0
    
    def test_compare_function_calls_empty(self):
        """Test function call comparison for empty calls."""
        calculator = MetricsCalculator()
        
        result = calculator.compare_function_calls([], [])
        assert result['exact_match'] == True
        assert result['similarity_score'] == 1.0
        
        result = calculator.compare_function_calls([{"function_name": "test"}], [])
        assert result['exact_match'] == False
        assert result['similarity_score'] == 0.0
    
    def test_evaluate_test_case_success(self, sample_test_case, sample_agent_result):
        """Test test case evaluation for successful cases."""
        calculator = MetricsCalculator()
        
        evaluation = calculator.evaluate_test_case(sample_agent_result, sample_test_case)
        
        assert evaluation['success'] == True
        assert evaluation['test_case_id'] == "ZRC_TC_001"
        assert evaluation['overall_match'] == True
        assert evaluation['function_calls_match'] == True
        assert evaluation['contract_selection_match'] == True
        assert evaluation['rewritten_query_similarity'] > 0.9
    
    def test_evaluate_test_case_failure(self, sample_test_case):
        """Test test case evaluation for failed cases."""
        calculator = MetricsCalculator()
        
        failed_result = {
            "success": False,
            "error": "Test error"
        }
        
        evaluation = calculator.evaluate_test_case(failed_result, sample_test_case)
        
        assert evaluation['success'] == False
        assert evaluation['overall_match'] == False
        assert evaluation['function_calls_match'] == False
        assert evaluation['rewritten_query_similarity'] == 0.0
    
    def test_calculate_aggregate_metrics_empty(self):
        """Test aggregate metrics calculation for empty evaluations."""
        calculator = MetricsCalculator()
        
        metrics = calculator.calculate_aggregate_metrics([])
        
        assert metrics.total_tests == 0
        assert metrics.successful_tests == 0
        assert metrics.accuracy == 0.0
    
    def test_calculate_aggregate_metrics_single_success(self):
        """Test aggregate metrics calculation for single successful test."""
        calculator = MetricsCalculator()
        
        evaluation = {
            'overall_match': True,
            'rewritten_query_similarity': 0.95,
            'contract_selection_match': True,
            'function_call_metrics': {
                'function_name_accuracy': 1.0,
                'parameter_accuracy': 1.0,
                'value_accuracy': 1.0,
                'function_name_match': True,
                'parameter_match': True,
                'value_match': True
            }
        }
        
        metrics = calculator.calculate_aggregate_metrics([evaluation])
        
        assert metrics.total_tests == 1
        assert metrics.successful_tests == 1
        assert metrics.accuracy == 1.0
        assert metrics.function_name_accuracy == 1.0
        assert metrics.contract_selection_accuracy == 1.0
    
    def test_generate_detailed_report(self):
        """Test detailed report generation."""
        calculator = MetricsCalculator()
        
        metrics = TestMetrics(
            total_tests=2,
            successful_tests=1,
            failed_tests=1,
            accuracy=0.5,
            function_name_accuracy=0.75,
            parameter_accuracy=0.6,
            value_accuracy=0.8,
            rewritten_query_similarity=0.7,
            contract_selection_accuracy=0.5,
            function_name_matches=1,
            parameter_matches=1,
            value_matches=1,
            contract_matches=1,
            reasoning_quality_score=0.68
        )
        
        evaluations = [
            {
                'test_case_id': 'ZRC_TC_001',
                'overall_match': True,
                'rewritten_query_similarity': 0.9,
                'contract_selection_match': True,
                'function_call_metrics': {'exact_match': True}
            },
            {
                'test_case_id': 'ZRC_TC_002',
                'overall_match': False,
                'error': 'Test failed',
                'rewritten_query_similarity': 0.5,
                'contract_selection_match': False,
                'function_call_metrics': {'exact_match': False}
            }
        ]
        
        report = calculator.generate_detailed_report(metrics, evaluations)
        
        assert "ZIRCUIT AGENT TEST REPORT" in report
        assert "Total Tests: 2" in report
        assert "Successful Tests: 1" in report
        assert "Overall Accuracy: 50.00%" in report
        assert "FAILED TEST CASES:" in report
        assert "ZRC_TC_002" in report


class TestTestMetrics:
    """Test cases for the TestMetrics dataclass."""
    
    def test_test_metrics_creation(self):
        """Test TestMetrics object creation."""
        metrics = TestMetrics(
            total_tests=10,
            successful_tests=8,
            failed_tests=2,
            accuracy=0.8,
            function_name_accuracy=0.9,
            parameter_accuracy=0.85,
            value_accuracy=0.95,
            rewritten_query_similarity=0.75,
            contract_selection_accuracy=0.9,
            function_name_matches=9,
            parameter_matches=8,
            value_matches=9,
            contract_matches=9,
            reasoning_quality_score=0.83
        )
        
        assert metrics.total_tests == 10
        assert metrics.successful_tests == 8
        assert metrics.accuracy == 0.8
        assert metrics.reasoning_quality_score == 0.83 