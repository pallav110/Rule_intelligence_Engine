#!/usr/bin/env python3
"""
Stress test script for Rule Intelligence Engine
Tests various edge cases and error conditions
"""

import requests
import json
import time
import sys
from typing import Dict, Any, List

API_BASE = "http://localhost:8000/v1"

def test_endpoint(endpoint: str, payload: Dict[str, Any], test_name: str) -> Dict[str, Any]:
    """Test a single endpoint and return results"""
    url = f"{API_BASE}{endpoint}"
    try:
        print(f"    → Testing: {test_name[:50]}{'...' if len(test_name) > 50 else ''}")
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=10)
        elapsed = time.time() - start_time

        result = {
            "test_name": test_name,
            "endpoint": endpoint,
            "status_code": response.status_code,
            "response_time": round(elapsed, 3),
            "success": 200 <= response.status_code < 300,
            "response_size": len(response.text),
        }

        # Try to parse JSON response
        try:
            result["response_json"] = response.json()
            # Print brief response info for successful tests
            if result["success"] and isinstance(result["response_json"], dict):
                status = result["response_json"].get("status", "unknown")
                print(f"    ✅ Status: {response.status_code} | Response: {status} | Time: {elapsed:.2f}s")
            elif result["success"]:
                print(f"    ✅ Status: {response.status_code} | Time: {elapsed:.2f}s")
            else:
                print(f"    ❌ Status: {response.status_code} | Time: {elapsed:.2f}s")
        except:
            result["response_text"] = response.text[:200]  # First 200 chars
            if result["success"]:
                print(f"    ✅ Status: {response.status_code} | Time: {elapsed:.2f}s")
            else:
                print(f"    ❌ Status: {response.status_code} | Time: {elapsed:.2f}s")

        return result
    except requests.exceptions.Timeout:
        print(f"    ❌ Timeout after 10s")
        return {
            "test_name": test_name,
            "endpoint": endpoint,
            "error": "Timeout",
            "success": False
        }
    except Exception as e:
        print(f"    ❌ Error: {str(e)}")
        return {
            "test_name": test_name,
            "endpoint": endpoint,
            "error": str(e),
            "success": False
        }

def run_stress_tests():
    """Run all stress tests"""
    print("Starting Rule Intelligence Engine Stress Tests")
    print("=" * 60)

    # Test cases organized by category
    test_cases = [
        # 1. Input Validation & Malformed Payloads
        {
            "category": "Input Validation",
            "tests": [
                {
                    "name": "Extremely long feedback (100k chars)",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "a" * 100000,
                        "workspace_id": "stress_test_ws"
                    }
                },
                {
                    "name": "Missing required fields",
                    "endpoint": "/feedback/analyze",
                    "payload": {}
                },
                {
                    "name": "Empty feedback text",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "",
                        "workspace_id": "test_ws"
                    }
                },
                {
                    "name": "Single character feedback",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "a",
                        "workspace_id": "test_ws"
                    }
                },
                {
                    "name": "SQL injection attempt",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue; DROP TABLE orders; --",
                        "workspace_id": "test_ws"
                    }
                },
                {
                    "name": "Unicode/emoji edge cases",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue 💸 should exclude cancelled orders 🚫✅",
                        "workspace_id": "test_ws"
                    }
                },
                {
                    "name": "Invalid JSON (handled by requests)",
                    "endpoint": "/feedback/analyze",
                    "payload": {"invalid": "json"},  # This is valid JSON, testing structure
                    "extra_note": "Testing malformed JSON would require raw request"
                }
            ]
        },

        # 2. Domain Detection & Schema Edge Cases
        {
            "category": "Domain Detection",
            "tests": [
                {
                    "name": "Gibberish with real words",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "xxxx revenue yyyy cancelled zzzz",
                        "workspace_id": "test_ws2"
                    }
                },
                {
                    "name": "Text matching NO domain",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "The quick brown fox jumps over the lazy dog",
                        "workspace_id": "test_ws3"
                    }
                },
                {
                    "name": "Ambiguous text (could match multiple domains)",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Users should be able to export data",
                        "workspace_id": "test_ws4"
                    }
                },
                {
                    "name": "Non-existent domain_pack_id",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue should exclude cancelled orders",
                        "workspace_id": "test_ws5",
                        "domain_pack_id": "nonexistent_domain"
                    }
                }
            ]
        },

        # 3. Model Fallback & Failure Scenarios
        {
            "category": "Model Behavior",
            "tests": [
                {
                    "name": "Force baseline mode",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue should exclude cancelled orders",
                        "workspace_id": "test_ws6"
                    },
                    "params": {"model": "baseline"}
                },
                {
                    "name": "All caps feedback",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "REVENUE EXCLUDE CANCELLED ORDERS!!!!",
                        "workspace_id": "test_ws7"
                    }
                },
                {
                    "name": "Mixed language/Hinglish",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue se cancelled orders exclude karna chahiye",
                        "workspace_id": "test_ws8"
                    }
                },
                {
                    "name": "Very short actionable feedback",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Exclude cancelled",
                        "workspace_id": "test_ws9"
                    }
                }
            ]
        },

        # 4. Workspace & Isolation Tests
        {
            "category": "Workspace Handling",
            "tests": [
                {
                    "name": "Auto-creation with new workspace ID",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Test feedback for new workspace",
                        "workspace_id": "brand_new_ws_12345"
                    }
                },
                {
                    "name": "Very long workspace ID",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Test feedback",
                        "workspace_id": "w" * 100
                    }
                },
                {
                    "name": "Special characters in workspace ID",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Test feedback",
                        "workspace_id": "ws-test_123.special@chars"
                    }
                }
            ]
        },

        # 5. Duplicate & Conflict Detection Edge Cases
        {
            "category": "Duplicate/Conflict Detection",
            "tests": [
                {
                    "name": "Near-duplicates: slight wording differences",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue must exclude cancelled orders",
                        "workspace_id": "test_dup_ws"
                    }
                },
                {
                    "name": "Opposing statements (potential conflict)",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue must include cancelled orders",
                        "workspace_id": "test_conflict_ws"
                    }
                },
                {
                    "name": "Complex conditions",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue from US customers should exclude cancelled orders over $100",
                        "workspace_id": "test_complex_ws"
                    }
                },
                {
                    "name": "Contradictory feedback",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue should exclude cancelled orders and also include cancelled orders",
                        "workspace_id": "test_contrad_ws"
                    }
                },
                {
                    "name": "Feedback with table references",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Total payments from the orders table should exclude refunds",
                        "workspace_id": "test_schema_ws3"
                    }
                },
                {
                    "name": "Feedback with qualified names (table.column)",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue should exclude orders.status = cancelled",
                        "workspace_id": "test_schema_ws4"
                    }
                }
            ]
        },

        # 6. Clarification Generation
        {
            "category": "Clarification Handling",
            "tests": [
                {
                    "name": "Vague feedback: Revenue needs fixing",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue needs fixing",
                        "workspace_id": "test_clar_ws"
                    }
                },
                {
                    "name": "Vague feedback: Calculation is wrong",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "The calculation is wrong",
                        "workspace_id": "test_clar_ws2"
                    }
                },
                {
                    "name": "Vague feedback: Change how we calculate",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "We need to change how we calculate things",
                        "workspace_id": "test_clar_ws3"
                    }
                },
                {
                    "name": "Missing business term/operation",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Orders should be excluded",
                        "workspace_id": "test_clar_ws4"
                    }
                },
                {
                    "name": "Missing how to calculate",
                    "endpoint": "/feedback/analyze",
                    "payload": {
                        "feedback_text": "Revenue should be calculated differently",
                        "workspace_id": "test_clar_ws5"
                    }
                }
            ]
        }
    ]

    all_results = []

    for category in test_cases:
        print(f"\n{category['category']} Tests:")
        print("-" * 40)

        for test in category["tests"]:
            # Handle parameters if present
            params = test.get("params", {})
            payload = test["payload"]

            # Add parameters to URL if needed
            endpoint = test["endpoint"]
            if params:
                # For simplicity, we'll add common params like model
                if "model" in params:
                    endpoint += f"?model={params['model']}"

            result = test_endpoint(endpoint, payload, test["name"])
            all_results.append(result)

            # Print brief result
            if result.get("success", False):
                status = f"✅ {result['status_code']} ({result['response_time']}s)"
            else:
                error_msg = result.get('error', f'Status {result.get("status_code", "Unknown")}')
                status = f"❌ {error_msg}"

            print(f"  {status} - {test['name']}")

            # Small delay to avoid overwhelming the server
            time.sleep(0.1)

    # Summary
    print("\n" + "=" * 60)
    print("STRESS TEST SUMMARY")
    print("=" * 60)

    total_tests = len(all_results)
    successful_tests = sum(1 for r in all_results if r.get("success", False))
    failed_tests = total_tests - successful_tests

    print(f"Total Tests: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success Rate: {successful_tests/total_tests*100:.1f}%")

    if failed_tests > 0:
        print("\nFailed Tests:")
        for result in all_results:
            if not result.get("success", False):
                error_msg = result.get('error', f"Status {result.get('status_code', 'Unknown')}")
                print(f"  ❌ {result['test_name']}: {error_msg}")

    # Save detailed results to file
    with open("stress_test_results.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nDetailed results saved to: stress_test_results.json")

    return failed_tests == 0

if __name__ == "__main__":
    success = run_stress_tests()
    sys.exit(0 if success else 1)