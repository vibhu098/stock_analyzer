"""Run the Stock Analysis Web Application with Claude/OpenAI Support"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run the Flask application with configurable LLM provider."""
    parser = argparse.ArgumentParser(description="Stock Analysis Web Application")
    parser.add_argument(
        "--provider",
        choices=["claude", "openai"],
        help="LLM provider to use (claude or openai)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run Flask server on (default: 5000)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=True,
        help="Enable debug mode (default: True)"
    )
    
    args = parser.parse_args()
    
    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Set LLM provider if specified
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
        logger.info(f"LLM Provider set to: {args.provider.upper()}")
    else:
        current_provider = os.environ.get("LLM_PROVIDER", "claude").lower()
        logger.info(f"Using default LLM Provider: {current_provider.upper()}")
    
    logger.info("Stock Analysis Web Application Startup")
    logger.info("=" * 50)
    
    # Check dependencies
    try:
        import flask
        logger.info("✓ Flask installed")
    except ImportError:
        logger.error("✗ Flask not installed. Run: pip install flask flask-cors")
        sys.exit(1)
    
    try:
        import pandas
        logger.info("✓ Pandas installed")
    except ImportError:
        logger.error("✗ Pandas not installed. Run: pip install pandas")
        sys.exit(1)
    
    # Check LLM provider
    if args.provider == "claude" or os.environ.get("LLM_PROVIDER", "claude").lower() == "claude":
        try:
            os.environ.get("ANTHROPIC_API_KEY")
            logger.info("✓ Claude provider configured")
        except Exception as e:
            logger.warning(f"Warning: {e}")
    elif args.provider == "openai" or os.environ.get("LLM_PROVIDER", "").lower() == "openai":
        try:
            os.environ.get("OPENAI_API_KEY")
            logger.info("✓ OpenAI provider configured")
        except Exception as e:
            logger.warning(f"Warning: {e}")
    
    try:
        from src.stock_analyzer.app import app
        logger.info("✓ Application imported successfully")
    except ImportError as e:
        logger.error(f"✗ Failed to import application: {e}")
        sys.exit(1)
    
    # Start Flask app
    logger.info("=" * 50)
    logger.info(f"Starting Flask server on {args.host}:{args.port}...")
    logger.info(f"Open browser: http://localhost:{args.port}")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 50)
    logger.info("")
    
    try:
        app.run(debug=args.debug, host=args.host, port=args.port)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    except Exception as e:
        logger.error(f"Error running application: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
