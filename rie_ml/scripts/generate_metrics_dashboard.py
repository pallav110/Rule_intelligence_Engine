#!/usr/bin/env python3
"""Generate HTML dashboard for baseline evaluation metrics.

Usage:
    python generate_metrics_dashboard.py              # Generate latest dashboard
    python generate_metrics_dashboard.py --all        # Include all historical data
    python generate_metrics_dashboard.py --id xyz     # Generate for specific evaluation
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any
import argparse
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.metrics_storage import MetricsStorage


class MetricsDashboard:
    """Generate HTML dashboard for metrics visualization."""

    def __init__(self):
        self.storage = MetricsStorage()
        self.dashboard_dir = self.storage.storage_dir / "dashboards"
        self.dashboard_dir.mkdir(exist_ok=True)

    def generate_evaluation_report(self, evaluation_id: str) -> Path:
        """Generate HTML report for a single evaluation."""
        result = self.storage.load_result(evaluation_id)
        if not result:
            print(f"❌ Evaluation not found: {evaluation_id}")
            return None

        html = self._build_evaluation_html(result)
        report_file = self.dashboard_dir / f"{evaluation_id}_report.html"

        with open(report_file, 'w') as f:
            f.write(html)

        return report_file

    def generate_comparison_dashboard(self, eval_id_1: str, eval_id_2: str) -> Path:
        """Generate comparison dashboard."""
        result1 = self.storage.load_result(eval_id_1)
        result2 = self.storage.load_result(eval_id_2)

        if not result1 or not result2:
            print("❌ One or both evaluations not found")
            return None

        comparison = self.storage.compare_results(eval_id_1, eval_id_2)
        html = self._build_comparison_html(result1, result2, comparison)
        report_file = self.dashboard_dir / f"comparison_{eval_id_1[:8]}_{eval_id_2[:8]}.html"

        with open(report_file, 'w') as f:
            f.write(html)

        return report_file

    def generate_history_dashboard(self, limit: int = 20) -> Path:
        """Generate historical comparison dashboard."""
        results_meta = self.storage.list_results(limit=limit)

        if not results_meta:
            print("❌ No evaluations found")
            return None

        # Load full results
        results = []
        for meta in results_meta:
            result = self.storage.load_result(meta["evaluation_id"])
            if result:
                results.append(result)

        html = self._build_history_html(results)
        report_file = self.dashboard_dir / "history_dashboard.html"

        with open(report_file, 'w') as f:
            f.write(html)

        return report_file

    def _build_evaluation_html(self, result: Any) -> str:
        """Build HTML for single evaluation report."""
        status_class = "pass" if result.acceptance_criteria_passed else "fail"
        status_text = "✅ PASSED" if result.acceptance_criteria_passed else "❌ FAILED"

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Baseline Evaluation Report - {result.evaluation_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .status {{
            display: inline-block;
            padding: 10px 20px;
            border-radius: 4px;
            font-weight: bold;
            margin-top: 15px;
            font-size: 1.2em;
        }}
        .status.pass {{
            background: #4caf50;
            color: white;
        }}
        .status.fail {{
            background: #f44336;
            color: white;
        }}
        .content {{
            padding: 40px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .info-card {{
            background: #f5f5f5;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #667eea;
        }}
        .info-card h3 {{
            color: #667eea;
            margin-bottom: 10px;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .info-card p {{
            color: #333;
            font-size: 1.3em;
            font-weight: bold;
            word-break: break-all;
        }}
        .metrics-section {{
            margin-bottom: 40px;
        }}
        .metrics-section h2 {{
            font-size: 1.5em;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}
        .metric-card {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 6px;
            padding: 20px;
            text-align: center;
        }}
        .metric-card h3 {{
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        .metric-value.percent::after {{
            content: '%';
            font-size: 0.6em;
        }}
        .metric-value.score {{
            font-size: 1.8em;
        }}
        .footer {{
            background: #f5f5f5;
            padding: 20px 40px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
        .note {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin-top: 20px;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Baseline Evaluation Report</h1>
            <p>Rule Intelligence Engine - Metrics & Performance Assessment</p>
            <div class="status {status_class}">{status_text}</div>
        </div>

        <div class="content">
            <div class="info-grid">
                <div class="info-card">
                    <h3>Evaluation ID</h3>
                    <p>{result.evaluation_id}</p>
                </div>
                <div class="info-card">
                    <h3>Timestamp</h3>
                    <p>{result.timestamp}</p>
                </div>
                <div class="info-card">
                    <h3>Model Type</h3>
                    <p>{result.model_type} v{result.model_version}</p>
                </div>
                <div class="info-card">
                    <h3>Dataset Split</h3>
                    <p>{result.dataset_split} ({result.dataset_size} samples)</p>
                </div>
            </div>

            <div class="metrics-section">
                <h2>📊 Classification Metrics</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Accuracy</h3>
                        <div class="metric-value percent">{result.classification.accuracy * 100:.1f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Calibration Error</h3>
                        <div class="metric-value score">{result.classification.calibration_error:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Total Samples</h3>
                        <div class="metric-value">{result.classification.total_samples}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Correct Predictions</h3>
                        <div class="metric-value">{result.classification.correct_predictions}</div>
                    </div>
                </div>
            </div>

            <div class="metrics-section">
                <h2>🔍 Rule Extraction Metrics</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Business Term F1</h3>
                        <div class="metric-value score">{result.extraction.business_term_f1:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Operation F1</h3>
                        <div class="metric-value score">{result.extraction.operation_f1:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Conditions F1</h3>
                        <div class="metric-value score">{result.extraction.conditions_f1:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Scope F1</h3>
                        <div class="metric-value score">{result.extraction.scope_f1:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Time Window F1</h3>
                        <div class="metric-value score">{result.extraction.time_window_f1:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Affected Entities F1</h3>
                        <div class="metric-value score">{result.extraction.affected_entities_f1:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Threshold F1</h3>
                        <div class="metric-value score">{result.extraction.threshold_f1:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Exact Rule Match Rate</h3>
                        <div class="metric-value percent">{result.extraction.exact_rule_match_rate * 100:.1f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Schema Validation Pass Rate</h3>
                        <div class="metric-value percent">{result.extraction.schema_validation_pass_rate * 100:.1f}</div>
                    </div>
                </div>
            </div>

            <div class="metrics-section">
                <h2>🔄 Duplicate Detection Metrics</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Precision</h3>
                        <div class="metric-value score">{result.duplicate_detection.precision:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Recall</h3>
                        <div class="metric-value score">{result.duplicate_detection.recall:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>F1 Score</h3>
                        <div class="metric-value score">{result.duplicate_detection.f1_score:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Recall@K</h3>
                        <div class="metric-value score">{result.duplicate_detection.recall_at_k:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>False Positive Rate</h3>
                        <div class="metric-value score">{result.duplicate_detection.false_positive_rate:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>False Negative Rate</h3>
                        <div class="metric-value score">{result.duplicate_detection.false_negative_rate:.4f}</div>
                    </div>
                </div>
            </div>

            <div class="metrics-section">
                <h2>⚠️ Conflict Detection Metrics</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Precision</h3>
                        <div class="metric-value score">{result.conflict_detection.precision:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Recall</h3>
                        <div class="metric-value score">{result.conflict_detection.recall:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>F1 Score</h3>
                        <div class="metric-value score">{result.conflict_detection.f1_score:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Accuracy</h3>
                        <div class="metric-value percent">{result.conflict_detection.accuracy * 100:.1f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>False Conflict Rate</h3>
                        <div class="metric-value score">{result.conflict_detection.false_conflict_rate:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Missed Conflict Rate</h3>
                        <div class="metric-value score">{result.conflict_detection.missed_conflict_rate:.4f}</div>
                    </div>
                </div>
            </div>

            <div class="metrics-section">
                <h2>💬 Clarification Metrics</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Detection Precision</h3>
                        <div class="metric-value score">{result.clarification.detection_precision:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Detection Recall</h3>
                        <div class="metric-value score">{result.clarification.detection_recall:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Detection F1 Score</h3>
                        <div class="metric-value score">{result.clarification.detection_f1_score:.4f}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Avg Resolution Time</h3>
                        <div class="metric-value">{result.clarification.average_resolution_time_seconds:.1f}s</div>
                    </div>
                </div>
            </div>

            <div class="metrics-section">
                <h2>⚡ Performance</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Avg Processing Time</h3>
                        <div class="metric-value">{result.average_processing_time_seconds:.4f}s</div>
                    </div>
                </div>
            </div>

            {f'<div class="note"><strong>Notes:</strong> {result.notes}</div>' if result.notes else ''}
        </div>

        <div class="footer">
            <p>Generated on {datetime.utcnow().isoformat()}Z | Rule Intelligence Engine Baseline Evaluation</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def _build_comparison_html(self, result1: Any, result2: Any, comparison: Dict) -> str:
        """Build HTML for comparison report."""
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Baseline Comparison Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .content {{
            padding: 40px;
        }}
        .comparison-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }}
        .eval-card {{
            background: #f5f5f5;
            padding: 20px;
            border-radius: 6px;
            border-top: 4px solid #667eea;
        }}
        .eval-card h3 {{
            color: #333;
            margin-bottom: 15px;
            font-size: 1.2em;
        }}
        .eval-info {{
            margin-bottom: 10px;
            font-size: 0.9em;
            color: #666;
        }}
        .eval-info strong {{
            color: #333;
        }}
        .improvements {{
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 20px;
        }}
        .improvements h3 {{
            color: #2e7d32;
            margin-bottom: 15px;
        }}
        .improvement-item {{
            margin-bottom: 10px;
            padding: 10px;
            background: white;
            border-radius: 4px;
        }}
        .improvement-item strong {{
            color: #2e7d32;
        }}
        .regressions {{
            background: #ffebee;
            border-left: 4px solid #f44336;
            padding: 20px;
            border-radius: 6px;
        }}
        .regressions h3 {{
            color: #c62828;
            margin-bottom: 15px;
        }}
        .regression-item {{
            margin-bottom: 10px;
            padding: 10px;
            background: white;
            border-radius: 4px;
        }}
        .regression-item strong {{
            color: #c62828;
        }}
        .footer {{
            background: #f5f5f5;
            padding: 20px 40px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Baseline Comparison Report</h1>
            <p>Model Performance Analysis & Improvement Tracking</p>
        </div>

        <div class="content">
            <div class="comparison-grid">
                <div class="eval-card">
                    <h3>📊 Baseline Evaluation</h3>
                    <div class="eval-info"><strong>ID:</strong> {result1.evaluation_id[:20]}...</div>
                    <div class="eval-info"><strong>Model:</strong> {result1.model_type}</div>
                    <div class="eval-info"><strong>Time:</strong> {result1.timestamp}</div>
                    <div class="eval-info"><strong>Classification Accuracy:</strong> {result1.classification.accuracy * 100:.2f}%</div>
                    <div class="eval-info"><strong>Extraction F1:</strong> {result1.extraction.exact_rule_match_rate:.4f}</div>
                </div>

                <div class="eval-card">
                    <h3>📊 Candidate Evaluation</h3>
                    <div class="eval-info"><strong>ID:</strong> {result2.evaluation_id[:20]}...</div>
                    <div class="eval-info"><strong>Model:</strong> {result2.model_type}</div>
                    <div class="eval-info"><strong>Time:</strong> {result2.timestamp}</div>
                    <div class="eval-info"><strong>Classification Accuracy:</strong> {result2.classification.accuracy * 100:.2f}%</div>
                    <div class="eval-info"><strong>Extraction F1:</strong> {result2.extraction.exact_rule_match_rate:.4f}</div>
                </div>
            </div>

            {self._build_improvements_html(comparison) if comparison.get("improvements") else ""}
            {self._build_regressions_html(comparison) if comparison.get("regressions") else ""}
        </div>

        <div class="footer">
            <p>Generated on {datetime.utcnow().isoformat()}Z</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def _build_improvements_html(self, comparison: Dict) -> str:
        """Build improvements section HTML."""
        html = '<div class="improvements"><h3>📈 Improvements</h3>'
        for metric, details in comparison["improvements"].items():
            html += f"""
            <div class="improvement-item">
                <strong>{metric.replace('_', ' ').title()}</strong><br/>
                Baseline: {details['baseline']:.4f} → Candidate: {details['candidate']:.4f}
                <br/><strong style="color: #2e7d32;">+{details['improvement']:.4f}</strong>
            </div>
            """
        html += '</div>'
        return html

    def _build_regressions_html(self, comparison: Dict) -> str:
        """Build regressions section HTML."""
        html = '<div class="regressions"><h3>📉 Regressions</h3>'
        for metric, details in comparison["regressions"].items():
            html += f"""
            <div class="regression-item">
                <strong>{metric.replace('_', ' ').title()}</strong><br/>
                Baseline: {details['baseline']:.4f} → Candidate: {details['candidate']:.4f}
                <br/><strong style="color: #c62828;">-{details['regression']:.4f}</strong>
            </div>
            """
        html += '</div>'
        return html

    def _build_history_html(self, results: List[Any]) -> str:
        """Build historical comparison HTML."""
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evaluation History Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .content { padding: 40px; }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }
        td {
            padding: 15px;
            border-bottom: 1px solid #ddd;
        }
        tr:hover { background: #f5f5f5; }
        .pass { color: #4caf50; font-weight: bold; }
        .fail { color: #f44336; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Evaluation History Dashboard</h1>
            <p>Baseline Model Performance Tracking Over Time</p>
        </div>
        <div class="content">
            <table>
                <thead>
                    <tr>
                        <th>Evaluation ID</th>
                        <th>Timestamp</th>
                        <th>Model Type</th>
                        <th>Classification Accuracy</th>
                        <th>Extraction F1</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
        for result in results:
            status_class = "pass" if result.acceptance_criteria_passed else "fail"
            status_text = "✅ PASS" if result.acceptance_criteria_passed else "❌ FAIL"
            html += f"""
                    <tr>
                        <td>{result.evaluation_id[:30]}...</td>
                        <td>{result.timestamp}</td>
                        <td>{result.model_type}</td>
                        <td>{result.classification.accuracy * 100:.2f}%</td>
                        <td>{result.extraction.exact_rule_match_rate:.4f}</td>
                        <td><span class="{status_class}">{status_text}</span></td>
                    </tr>
"""
        html += """
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""
        return html


def main():
    parser = argparse.ArgumentParser(description="Generate HTML metrics dashboard")
    parser.add_argument("--id", help="Generate report for specific evaluation")
    parser.add_argument("--compare", nargs=2, metavar=("ID1", "ID2"), help="Compare two evaluations")
    parser.add_argument("--history", action="store_true", help="Generate history dashboard")
    parser.add_argument("--all", action="store_true", help="Include all historical data")

    args = parser.parse_args()

    dashboard = MetricsDashboard()

    if args.id:
        report_file = dashboard.generate_evaluation_report(args.id)
        if report_file:
            print(f"✅ Report generated: {report_file}")
    elif args.compare:
        report_file = dashboard.generate_comparison_dashboard(args.compare[0], args.compare[1])
        if report_file:
            print(f"✅ Comparison generated: {report_file}")
    elif args.history or args.all:
        limit = None if args.all else 20
        report_file = dashboard.generate_history_dashboard(limit=limit)
        if report_file:
            print(f"✅ History dashboard generated: {report_file}")
    else:
        print("❌ Please specify --id, --compare, or --history")
        sys.exit(1)


if __name__ == "__main__":
    main()
