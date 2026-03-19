"""
Agent Test Suite - Console Output
=================================
Run this file to test all agents:
    cd D:\portfolio\medtracker
    python -m backend.tests.test_agents

Or directly:
    python backend/tests/test_agents.py
"""

import asyncio
import sys
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, 'D:/portfolio/medtracker')

from backend.agents import (
    AgentInput,
    ClassifierAgent,
    InteractionCheckerAgent,
    SafetyReviewerAgent,
    ResponseGeneratorAgent,
)
from backend.core.guardrails import SafetyFlag


# ANSI color codes for pretty console output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


@dataclass
class TestCase:
    """A single test case"""
    name: str
    input_data: AgentInput
    expected_intent: Optional[str] = None
    expected_contains: List[str] = None
    expected_not_contains: List[str] = None
    should_have_safety_flags: bool = False
    should_succeed: bool = True


@dataclass
class TestResult:
    """Result of running a test"""
    test_name: str
    passed: bool
    duration_ms: float
    errors: List[str]
    agent_response: str
    safety_flags: List[SafetyFlag]
    metadata: Dict


class AgentTestSuite:
    """Test suite for MedTracker agents"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.agents = {}
        self._setup_agents()
    
    def _setup_agents(self):
        """Initialize all agents"""
        print(f"{Colors.OKBLUE}Initializing agents...{Colors.ENDC}")
        
        # Create agents without LLM for testing (deterministic)
        self.agents['classifier'] = ClassifierAgent(
            enable_logging=False  # Reduce noise in tests
        )
        self.agents['interaction'] = InteractionCheckerAgent(
            enable_logging=False
        )
        self.agents['safety'] = SafetyReviewerAgent(
            strict_mode=True,
            enable_logging=False
        )
        self.agents['generator'] = ResponseGeneratorAgent(
            enable_logging=False
        )
        
        print(f"{Colors.OKGREEN}[OK] Agents initialized{Colors.ENDC}\n")
    
    # ==================== TEST CASES ====================
    
    def get_classifier_tests(self) -> List[TestCase]:
        """Test cases for ClassifierAgent"""
        return [
            TestCase(
                name="emergency_overdose",
                input_data=AgentInput(
                    query="I took 20 pills of aspirin, what should I do?",
                    session_id="test_1"
                ),
                expected_intent="emergency",
                should_have_safety_flags=True
            ),
            TestCase(
                name="emergency_chest_pain",
                input_data=AgentInput(
                    query="I'm having chest pain after taking medication",
                    session_id="test_2"
                ),
                expected_intent="emergency",
                should_have_safety_flags=True
            ),
            TestCase(
                name="interaction_check",
                input_data=AgentInput(
                    query="Can I take ibuprofen with my blood pressure medication?",
                    session_id="test_3"
                ),
                expected_intent="interaction_check"
            ),
            TestCase(
                name="dosage_question",
                input_data=AgentInput(
                    query="What should I do if I miss a dose of my medication?",
                    session_id="test_4"
                ),
                expected_intent="dosage_question"
            ),
            TestCase(
                name="side_effects",
                input_data=AgentInput(
                    query="What are the side effects of metformin?",
                    session_id="test_5"
                ),
                expected_intent="side_effects"
            ),
            TestCase(
                name="medication_info",
                input_data=AgentInput(
                    query="What is lisinopril used for?",
                    session_id="test_6"
                ),
                expected_intent="medication_info"
            ),
            TestCase(
                name="general_chat",
                input_data=AgentInput(
                    query="Hello, can you help me?",
                    session_id="test_7"
                ),
                expected_intent="general_chat"
            ),
            TestCase(
                name="pii_detection_ssn",
                input_data=AgentInput(
                    query="My SSN is 123-45-6789 and I need medication help",
                    session_id="test_8"
                ),
                should_have_safety_flags=True  # PII detected
            ),
        ]
    
    def get_interaction_tests(self) -> List[TestCase]:
        """Test cases for InteractionCheckerAgent"""
        return [
            TestCase(
                name="warfarin_ibuprofen_severe",
                input_data=AgentInput(
                    query="Can I take ibuprofen with warfarin?",
                    user_medications=[{"name": "warfarin 5mg", "dosage": "5mg", "frequency": "daily"}],
                    session_id="test_9"
                ),
                expected_contains=["severe", "bleeding", "avoid"],
                should_have_safety_flags=True
            ),
            TestCase(
                name="no_interaction_found",
                input_data=AgentInput(
                    query="Can I take vitamin D with my medication?",
                    user_medications=[{"name": "lisinopril", "dosage": "10mg", "frequency": "daily"}],
                    session_id="test_10"
                ),
                expected_contains=["No known interactions"]
            ),
            TestCase(
                name="allergy_concern",
                input_data=AgentInput(
                    query="Can I take amoxicillin?",
                    user_medications=[],
                    allergies=["penicillin"],
                    session_id="test_11"
                ),
                expected_contains=["allergy", "DO NOT"],
                should_have_safety_flags=True
            ),
            TestCase(
                name="duplicate_therapy_nsaid",
                input_data=AgentInput(
                    query="Can I take ibuprofen?",
                    user_medications=[{"name": "naproxen 500mg", "dosage": "500mg", "frequency": "twice daily"}],
                    session_id="test_12"
                ),
                expected_contains=["duplicate", "NSAID"]
            ),
            TestCase(
                name="lisinopril_potassium",
                input_data=AgentInput(
                    query="Is it safe to take potassium supplements with lisinopril?",
                    user_medications=[{"name": "lisinopril 10mg", "dosage": "10mg", "frequency": "daily"}],
                    session_id="test_13"
                ),
                expected_contains=[["potassium", "hyperkalemia"]]
            ),
        ]
    
    def get_safety_reviewer_tests(self) -> List[TestCase]:
        """Test cases for SafetyReviewerAgent"""
        return [
            TestCase(
                name="safe_response",
                input_data=AgentInput(
                    query='{"response": "You should consult your doctor about this medication.", "original_question": "What should I do?", "context": {"intent": "medication_info"}}',
                    session_id="test_14"
                ),
                should_succeed=True
            ),
            TestCase(
                name="dangerous_content",
                input_data=AgentInput(
                    query='{"response": "Stop taking your medication immediately and double the dose of aspirin.", "original_question": "My medication makes me tired", "context": {"intent": "side_effects"}}',
                    session_id="test_15"
                ),
                expected_contains=["is_safe", "false"],
                should_succeed=True  # Review succeeds but flags issues
            ),
            TestCase(
                name="missing_disclaimer",
                input_data=AgentInput(
                    query='{"response": "Take 2 pills every day.", "original_question": "How much should I take?", "context": {"intent": "dosage_question"}}',
                    session_id="test_16"
                ),
                expected_contains=["missing_disclaimer"]
            ),
            TestCase(
                name="pii_in_response",
                input_data=AgentInput(
                    query='{"response": "Patient John Doe, SSN 123-45-6789, should take this medication.", "original_question": "Should I take this?", "context": {"intent": "medication_info"}}',
                    session_id="test_17"
                ),
                expected_contains=["pii"]
            ),
        ]
    
    def get_generator_tests(self) -> List[TestCase]:
        """Test cases for ResponseGeneratorAgent"""
        return [
            TestCase(
                name="emergency_template",
                input_data=AgentInput(
                    query="I overdosed on medication",
                    context={"intent": "emergency"},
                    session_id="test_18"
                ),
                expected_contains=["911", "emergency", "Poison Control"],
                expected_not_contains=["medical disclaimer"]  # Emergency has different footer
            ),
            TestCase(
                name="general_chat_template",
                input_data=AgentInput(
                    query="Hello",
                    context={"intent": "general_chat"},
                    session_id="test_19"
                ),
                expected_contains=["Hello", "medication assistant"]
            ),
            TestCase(
                name="interaction_with_data",
                input_data=AgentInput(
                    query="Can I take ibuprofen with warfarin?",
                    context={
                        "intent": "interaction_check",
                        "interactions": {
                            "interactions": [
                                {"drug_a": "warfarin", "drug_b": "ibuprofen", "severity": "severe"}
                            ]
                        }
                    },
                    user_medications=[{"name": "warfarin", "dosage": "5mg", "frequency": "daily"}],
                    session_id="test_20"
                ),
                expected_contains=["consult", "healthcare"]
            ),
            TestCase(
                name="fallback_no_llm",
                input_data=AgentInput(
                    query="What are the side effects of metformin?",
                    context={"intent": "side_effects"},
                    session_id="test_21"
                ),
                expected_contains=["side effects", "contact", "doctor"]
            ),
        ]
    
    # ==================== TEST RUNNER ====================
    
    async def run_test(self, agent_name: str, test: TestCase) -> TestResult:
        """Run a single test case"""
        agent = self.agents[agent_name]
        errors = []
        
        start_time = time.time()
        
        try:
            output = await agent.run(test.input_data)
            duration_ms = (time.time() - start_time) * 1000
            
            # Check success
            if test.should_succeed and not output.success:
                errors.append(f"Expected success but got failure: {output.response}")
            
            # Check expected intent (for classifier)
            if test.expected_intent:
                actual_intent = output.response
                if actual_intent != test.expected_intent:
                    errors.append(f"Expected intent '{test.expected_intent}', got '{actual_intent}'")
            
            # Check expected content
            if test.expected_contains:
                response_lower = output.response.lower()
                for expected in test.expected_contains:
                    if isinstance(expected, list):
                        # Any of these options should be present
                        if not any(opt.lower() in response_lower for opt in expected):
                            errors.append(f"Response missing any of: {expected}")
                    else:
                        if expected.lower() not in response_lower:
                            errors.append(f"Response missing expected content: '{expected}'")
            
            # Check forbidden content
            if test.expected_not_contains:
                response_lower = output.response.lower()
                for forbidden in test.expected_not_contains:
                    if forbidden.lower() in response_lower:
                        errors.append(f"Response contains forbidden content: '{forbidden}'")
            
            # Check safety flags
            has_safety_flags = len(output.safety_flags) > 0
            if test.should_have_safety_flags and not has_safety_flags:
                errors.append("Expected safety flags but none found")
            if not test.should_have_safety_flags and has_safety_flags:
                errors.append(f"Unexpected safety flags: {[f.message for f in output.safety_flags]}")
            
            return TestResult(
                test_name=test.name,
                passed=len(errors) == 0,
                duration_ms=duration_ms,
                errors=errors,
                agent_response=output.response[:200] + "..." if len(output.response) > 200 else output.response,
                safety_flags=output.safety_flags,
                metadata=output.metadata
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return TestResult(
                test_name=test.name,
                passed=False,
                duration_ms=duration_ms,
                errors=[f"Exception: {str(e)}"],
                agent_response="",
                safety_flags=[],
                metadata={}
            )
    
    async def run_agent_tests(self, agent_name: str, tests: List[TestCase]) -> List[TestResult]:
        """Run all tests for an agent"""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}Testing: {agent_name.upper()}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
        
        results = []
        for test in tests:
            result = await self.run_test(agent_name, test)
            results.append(result)
            self._print_test_result(result)
        
        return results
    
    def _print_test_result(self, result: TestResult):
        """Pretty print a test result"""
        status = f"{Colors.OKGREEN}[PASS]{Colors.ENDC}" if result.passed else f"{Colors.FAIL}[FAIL]{Colors.ENDC}"
        print(f"\n{status} {Colors.BOLD}{result.test_name}{Colors.ENDC} ({result.duration_ms:.1f}ms)")
        
        if not result.passed:
            for error in result.errors:
                print(f"  {Colors.FAIL}  -> {error}{Colors.ENDC}")
        
        if result.safety_flags:
            print(f"  {Colors.WARNING}  Safety flags:{Colors.ENDC}")
            for flag in result.safety_flags:
                print(f"    - [{flag.level}] {flag.message}")
        
        if result.passed:
            print(f"  {Colors.OKCYAN}  Response: {result.agent_response[:80]}...{Colors.ENDC}")
    
    def print_summary(self, all_results: Dict[str, List[TestResult]]):
        """Print test summary"""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}TEST SUMMARY{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}\n")
        
        total_tests = 0
        total_passed = 0
        total_time = 0
        
        for agent_name, results in all_results.items():
            passed = sum(1 for r in results if r.passed)
            failed = len(results) - passed
            time_ms = sum(r.duration_ms for r in results)
            
            total_tests += len(results)
            total_passed += passed
            total_time += time_ms
            
            status_color = Colors.OKGREEN if failed == 0 else Colors.WARNING if failed < 3 else Colors.FAIL
            
            print(f"{Colors.BOLD}{agent_name:20}{Colors.ENDC} "
                  f"{status_color}{passed:2} passed{Colors.ENDC} | "
                  f"{Colors.FAIL if failed > 0 else Colors.OKGREEN}{failed:2} failed{Colors.ENDC} | "
                  f"{time_ms:6.1f}ms")
        
        print(f"\n{Colors.HEADER}{'-'*60}{Colors.ENDC}")
        
        pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        overall_color = Colors.OKGREEN if pass_rate == 100 else Colors.WARNING if pass_rate >= 80 else Colors.FAIL
        
        print(f"{Colors.BOLD}TOTAL:{Colors.ENDC} "
              f"{total_tests} tests | "
              f"{overall_color}{total_passed} passed ({pass_rate:.1f}%){Colors.ENDC} | "
              f"{total_time:.1f}ms")
        
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}\n")
        
        return total_passed == total_tests
    
    async def run_all_tests(self):
        """Run the complete test suite"""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.OKCYAN}MEDTRACKER AGENT TEST SUITE{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        all_results = {}
        
        # Run tests for each agent
        all_results['classifier'] = await self.run_agent_tests(
            'classifier', 
            self.get_classifier_tests()
        )
        
        all_results['interaction'] = await self.run_agent_tests(
            'interaction',
            self.get_interaction_tests()
        )
        
        all_results['safety'] = await self.run_agent_tests(
            'safety',
            self.get_safety_reviewer_tests()
        )
        
        all_results['generator'] = await self.run_agent_tests(
            'generator',
            self.get_generator_tests()
        )
        
        # Print summary
        all_passed = self.print_summary(all_results)
        
        # Agent health checks
        print(f"\n{Colors.HEADER}AGENT HEALTH CHECKS{Colors.ENDC}\n")
        for name, agent in self.agents.items():
            health = agent.health_check()
            status_color = Colors.OKGREEN if health['status'] == 'healthy' else Colors.WARNING if health['status'] == 'degraded' else Colors.FAIL
            print(f"{name:20} {status_color}{health['status']}{Colors.ENDC} "
                  f"(errors: {health['error_rate_24h']:.1%})")
        
        print()
        return all_passed


async def main():
    """Main entry point"""
    suite = AgentTestSuite()
    all_passed = await suite.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
