#!/usr/bin/env python
"""
Stock Analysis Web Application - Root Level Launcher
Runs from project root: python run.py [--provider claude|openai]

Usage Examples:
  python run.py                    # Uses default provider (Claude)
  python run.py --provider claude  # Explicitly use Claude
  python run.py --provider openai  # Use OpenAI
"""

import subprocess
import sys
import os
from pathlib import Path
import argparse

def main():
    """Launch the stock analysis web application."""
    parser = argparse.ArgumentParser(
        description="Stock Analysis Web Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                    # Use default provider (Claude)
  python run.py --provider claude  # Explicitly use Claude
  python run.py --provider openai  # Use OpenAI (requires OPENAI_API_KEY)

Configuration:
  - Set LLM_PROVIDER in .env file as default
  - Override with --provider argument
  - Ensure API keys are set (ANTHROPIC_API_KEY or OPENAI_API_KEY)
        """
    )
    parser.add_argument(
        "--provider",
        choices=["claude", "openai"],
        help="LLM provider to use (overrides LLM_PROVIDER env var)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run Flask server on (default: 5000)"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind to (default: localhost)"
    )
    
    args = parser.parse_args()
    
    # Get project root
    project_root = Path(__file__).parent
    
    # Change to project root
    os.chdir(project_root)
    
    # Set LLM provider if specified
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
        print(f"✓ Using LLM Provider: {args.provider.upper()}\n")
    else:
        current_provider = os.environ.get("LLM_PROVIDER", "claude").lower()
        print(f"✓ Using default LLM Provider: {current_provider.upper()}\n")
    
    # Run the src/run.py script with arguments
    src_run_script = project_root / "src" / "run.py"
    
    if not src_run_script.exists():
        print(f"✗ Error: {src_run_script} not found")
        sys.exit(1)
    
    # Execute src/run.py with provider info
    cmd = [
        sys.executable,
        str(src_run_script),
        "--port", str(args.port),
        "--host", args.host
    ]
    
    if args.provider:
        cmd.extend(["--provider", args.provider])
    
    result = subprocess.run(cmd, cwd=str(project_root))
    
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()

