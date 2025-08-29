"""
Python Code Analyzer
Analyzes Python files for common errors and issues
Usage: python code_analyzer.py [directory_path]
"""

import os
import re
import ast
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

class CodeAnalyzer:
    def __init__(self):
        self.issues = []
        self.file_count = 0
        self.error_patterns = {
            'string_division': {
                'pattern': r'(\w+)\s*\/\s*(\w+)',
                'description': 'Potential string division - variables may be strings instead of numbers',
                'severity': 'CRITICAL',
                'suggestion': 'Use pd.to_numeric() or float() to convert strings to numbers before division'
            },
            'csv_no_dtype': {
                'pattern': r'read_csv\([^)]*\)(?!.*dtype)',
                'description': 'CSV read without explicit data types',
                'severity': 'WARNING',
                'suggestion': 'Add dtype parameter or use pd.to_numeric() after reading'
            },
            'pandas_no_import': {
                'pattern': r'pd\.',
                'description': 'Using pandas without import statement',
                'severity': 'ERROR',
                'suggestion': 'Add: import pandas as pd'
            },
            'input_math': {
                'pattern': r'input\([^)]*\).*[+\-*/]',
                'description': 'Using input() result in mathematical operations',
                'severity': 'CRITICAL',
                'suggestion': 'Convert input to number: float(input()) or int(input())'
            },
            'missing_error_handling': {
                'pattern': r'to_numeric\([^)]*\)(?!.*errors=)',
                'description': 'to_numeric without error handling',
                'severity': 'WARNING',
                'suggestion': 'Add errors="coerce" parameter or use try/except block'
            },
            'string_concatenation_in_path': {
                'pattern': r'[\'"]\s*\+\s*.*\s*\+\s*[\'"]',
                'description': 'String concatenation for file paths',
                'severity': 'INFO',
                'suggestion': 'Use os.path.join() or pathlib for better path handling'
            }
        }

    def analyze_file(self, file_path: Path) -> List[Dict]:
        """Analyze a single Python file for issues"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Check for pandas import
            has_pandas_import = 'import pandas' in content
            
            for line_num, line in enumerate(lines, 1):
                line_stripped = line.strip()
                
                if not line_stripped or line_stripped.startswith('#'):
                    continue
                
                # Check each error pattern
                for error_type, pattern_info in self.error_patterns.items():
                    if re.search(pattern_info['pattern'], line_stripped):
                        # Special case: skip pandas check if import exists
                        if error_type == 'pandas_no_import' and has_pandas_import:
                            continue
                            
                        issues.append({
                            'file': str(file_path),
                            'line': line_num,
                            'type': error_type,
                            'severity': pattern_info['severity'],
                            'description': pattern_info['description'],
                            'suggestion': pattern_info['suggestion'],
                            'code': line_stripped
                        })
            
            # Additional AST-based analysis for more complex patterns
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                        line_num = getattr(node, 'lineno', 0)
                        if line_num > 0:
                            issues.append({
                                'file': str(file_path),
                                'line': line_num,
                                'type': 'ast_division',
                                'severity': 'WARNING',
                                'description': 'Division operation detected - verify operand types',
                                'suggestion': 'Ensure both operands are numeric types',
                                'code': lines[line_num - 1].strip() if line_num <= len(lines) else ''
                            })
            except SyntaxError:
                issues.append({
                    'file': str(file_path),
                    'line': 0,
                    'type': 'syntax_error',
                    'severity': 'CRITICAL',
                    'description': 'Syntax error in file',
                    'suggestion': 'Fix syntax errors before running',
                    'code': 'Syntax error prevents parsing'
                })
                
        except Exception as e:
            issues.append({
                'file': str(file_path),
                'line': 0,
                'type': 'file_error',
                'severity': 'ERROR',
                'description': f'Error reading file: {str(e)}',
                'suggestion': 'Check file permissions and encoding',
                'code': ''
            })
        
        return issues

    def analyze_directory(self, directory: Path) -> None:
        """Analyze all Python files in a directory"""
        python_files = list(directory.rglob('*.py'))
        
        if not python_files:
            print(f"No Python files found in {directory}")
            return
        
        print(f"Analyzing {len(python_files)} Python files...")
        
        for file_path in python_files:
            self.file_count += 1
            file_issues = self.analyze_file(file_path)
            self.issues.extend(file_issues)
            
            # Progress indicator
            if self.file_count % 10 == 0:
                print(f"Analyzed {self.file_count} files...")

    def generate_report(self, output_file: str = None) -> str:
        """Generate a detailed analysis report"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("PYTHON CODE ANALYSIS REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Files analyzed: {self.file_count}")
        report_lines.append(f"Total issues found: {len(self.issues)}")
        report_lines.append("")
        
        # Summary by severity
        severity_counts = {}
        for issue in self.issues:
            severity = issue['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        report_lines.append("SUMMARY BY SEVERITY:")
        report_lines.append("-" * 40)
        for severity in ['CRITICAL', 'ERROR', 'WARNING', 'INFO']:
            count = severity_counts.get(severity, 0)
            report_lines.append(f"{severity:<10}: {count:>3} issues")
        report_lines.append("")
        
        # Group issues by file
        issues_by_file = {}
        for issue in self.issues:
            file_path = issue['file']
            if file_path not in issues_by_file:
                issues_by_file[file_path] = []
            issues_by_file[file_path].append(issue)
        
        # Sort files by number of issues (most problematic first)
        sorted_files = sorted(issues_by_file.items(), 
                            key=lambda x: len(x[1]), reverse=True)
        
        report_lines.append("DETAILED ANALYSIS:")
        report_lines.append("-" * 80)
        
        for file_path, file_issues in sorted_files:
            report_lines.append(f"\nFILE: {file_path}")
            report_lines.append(f"Issues: {len(file_issues)}")
            report_lines.append("-" * 60)
            
            # Sort issues by line number
            file_issues.sort(key=lambda x: x['line'])
            
            for issue in file_issues:
                report_lines.append(f"  Line {issue['line']:>3} | {issue['severity']:<8} | {issue['description']}")
                if issue['code']:
                    report_lines.append(f"      Code: {issue['code']}")
                report_lines.append(f"      Fix:  {issue['suggestion']}")
                report_lines.append("")
        
        # Most common issues
        issue_type_counts = {}
        for issue in self.issues:
            issue_type = issue['type']
            issue_type_counts[issue_type] = issue_type_counts.get(issue_type, 0) + 1
        
        if issue_type_counts:
            report_lines.append("\nMOST COMMON ISSUES:")
            report_lines.append("-" * 40)
            sorted_types = sorted(issue_type_counts.items(), 
                                key=lambda x: x[1], reverse=True)
            for issue_type, count in sorted_types[:10]:
                report_lines.append(f"{issue_type:<25}: {count:>3} occurrences")
        
        # Quick fix suggestions
        report_lines.append("\n\nQUICK FIX SUGGESTIONS:")
        report_lines.append("-" * 40)
        report_lines.append("1. For string division errors:")
        report_lines.append("   - Use pd.to_numeric(df['column'], errors='coerce')")
        report_lines.append("   - Or df['column'].astype(float)")
        report_lines.append("")
        report_lines.append("2. For CSV data type issues:")
        report_lines.append("   - Add dtype parameter: pd.read_csv('file.csv', dtype={'col': float})")
        report_lines.append("   - Or convert after reading: df['col'] = pd.to_numeric(df['col'])")
        report_lines.append("")
        report_lines.append("3. For input() in math operations:")
        report_lines.append("   - Convert input: result = float(input('Enter number: ')) / 2")
        report_lines.append("")
        
        report_text = "\n".join(report_lines)
        
        # Write to file if specified
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            print(f"Report saved to: {output_file}")
        
        return report_text

def main():
    parser = argparse.ArgumentParser(description='Analyze Python code for common errors')
    parser.add_argument('directory', nargs='?', default='.', 
                       help='Directory to analyze (default: current directory)')
    parser.add_argument('-o', '--output', 
                       help='Output file for the report (default: print to console)')
    parser.add_argument('--format', choices=['text', 'html'], default='text',
                       help='Report format (default: text)')
    
    args = parser.parse_args()
    
    # Validate directory
    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory '{directory}' does not exist")
        sys.exit(1)
    
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory")
        sys.exit(1)
    
    # Run analysis
    print(f"Starting analysis of directory: {directory.absolute()}")
    analyzer = CodeAnalyzer()
    analyzer.analyze_directory(directory)
    
    # Generate report
    output_file = args.output
    if not output_file and analyzer.issues:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"code_analysis_report_{timestamp}.txt"
    
    if analyzer.issues:
        report = analyzer.generate_report(output_file)
        if not args.output:
            print("\n" + report)
    else:
        print("✅ No issues found in your code!")
    
    print(f"\nAnalysis complete. Checked {analyzer.file_count} files.")

if __name__ == "__main__":
    main()