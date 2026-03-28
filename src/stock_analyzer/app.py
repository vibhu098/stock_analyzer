"""Flask API for stock analysis service."""

import logging
import json
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import threading
from playwright.sync_api import sync_playwright
from src.stock_analyzer.analysis_engine import StockAnalysisEngine
from src.config import settings

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Get project root and configure paths
project_root = Path(__file__).parent.parent.parent
template_folder = project_root / "src" / "templates"
static_folder = project_root / "src" / "static"

# Initialize Flask app with proper paths
app = Flask(
    __name__,
    template_folder=str(template_folder),
    static_folder=str(static_folder),
    static_url_path="/static"
)
CORS(app)

# Initialize analysis engine with configured LLM provider
# Can be overridden via LLM_PROVIDER environment variable (openai or claude)
analysis_engine = StockAnalysisEngine(llm_provider=settings.llm_provider)

# Store analysis results and status
analysis_results = {}
analysis_status = {}


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    """Get list of available stocks."""
    try:
        stocks = analysis_engine.get_available_stocks()
        return jsonify({
            'success': True,
            'stocks': stocks,
            'count': len(stocks)
        })
    except Exception as e:
        logger.error(f"Error getting stocks: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Start stock analysis."""
    try:
        data = request.json
        stock_symbol = data.get('stock_symbol', '').upper()
        
        if not stock_symbol:
            return jsonify({
                'success': False,
                'error': 'Stock symbol is required'
            }), 400
        
        # Check if stock is available
        available_stocks = analysis_engine.get_available_stocks()
        if stock_symbol not in available_stocks:
            return jsonify({
                'success': False,
                'error': f'Stock {stock_symbol} not found in available data'
            }), 404
        
        # Set initial status
        analysis_status[stock_symbol] = {
            'status': 'processing',
            'message': 'Starting analysis...',
            'progress': 0
        }
        
        # Run analysis in background thread
        thread = threading.Thread(
            target=_run_analysis,
            args=(stock_symbol,),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'stock_symbol': stock_symbol,
            'message': 'Analysis started'
        })
    except Exception as e:
        logger.error(f"Error starting analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _run_analysis(stock_symbol: str):
    """Run analysis in background thread."""
    try:
        logger.info(f"Running analysis for {stock_symbol}")
        analysis_status[stock_symbol] = {
            'status': 'processing',
            'message': 'Loading data and generating analysis...',
            'progress': 10
        }
        
        # Run the analysis
        report = analysis_engine.get_analysis_report(stock_symbol)
        
        # Store results
        analysis_results[stock_symbol] = report
        analysis_status[stock_symbol] = {
            'status': 'completed',
            'message': 'Analysis completed successfully',
            'progress': 100
        }
        
        logger.info(f"Analysis completed for {stock_symbol}")
    except Exception as e:
        logger.error(f"Error in analysis for {stock_symbol}: {e}")
        analysis_status[stock_symbol] = {
            'status': 'error',
            'message': f'Error: {str(e)}',
            'progress': 0
        }
        analysis_results[stock_symbol] = {
            'error': str(e)
        }


@app.route('/api/status/<stock_symbol>', methods=['GET'])
def get_status(stock_symbol):
    """Get analysis status."""
    try:
        stock_symbol = stock_symbol.upper()
        status = analysis_status.get(stock_symbol, {
            'status': 'not_started',
            'message': 'Analysis not started',
            'progress': 0
        })
        
        return jsonify({
            'success': True,
            'stock_symbol': stock_symbol,
            'status': status
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/results/<stock_symbol>', methods=['GET'])
def get_results(stock_symbol):
    """Get analysis results."""
    try:
        stock_symbol = stock_symbol.upper()
        
        if stock_symbol not in analysis_results:
            return jsonify({
                'success': False,
                'error': 'No analysis results found. Please run analysis first.'
            }), 404
        
        report = analysis_results[stock_symbol]
        
        if report.get('error'):
            return jsonify({
                'success': False,
                'error': report['error']
            }), 400
        
        return jsonify({
            'success': True,
            'stock_symbol': stock_symbol,
            'report': report
        })
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/report/<stock_symbol>', methods=['GET'])
def view_report(stock_symbol):
    """View full HTML report for stock."""
    try:
        stock_symbol = stock_symbol.upper()
        
        if stock_symbol not in analysis_results:
            return jsonify({
                'success': False,
                'error': 'No analysis results found. Please run analysis first.'
            }), 404
        
        report = analysis_results[stock_symbol]
        
        if report.get('error'):
            return f"<h2>Error: {report['error']}</h2>", 400
        
        # Return the HTML report directly
        html_report = report.get('final_report', '')
        if html_report:
            return html_report, 200, {'Content-Type': 'text/html; charset=utf-8'}
        else:
            return "<h2>No report generated</h2>", 404
    except Exception as e:
        logger.error(f"Error viewing report: {e}")
        return f"<h2>Error: {str(e)}</h2>", 500


@app.route('/report/<stock_symbol>/pdf', methods=['GET'])
def export_pdf(stock_symbol):
    """Render the HTML report to PDF using Playwright and return it as a download."""
    try:
        stock_symbol = stock_symbol.upper()

        if stock_symbol not in analysis_results:
            return jsonify({'success': False, 'error': 'No analysis results found. Please run analysis first.'}), 404

        report = analysis_results[stock_symbol]
        if report.get('error'):
            return jsonify({'success': False, 'error': report['error']}), 400

        html_report = report.get('final_report', '')
        if not html_report:
            return jsonify({'success': False, 'error': 'No report generated'}), 404

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_report, wait_until='networkidle')
            pdf_bytes = page.pdf(
                format='A4',
                margin={'top': '15mm', 'bottom': '15mm', 'left': '12mm', 'right': '12mm'},
                print_background=True
            )
            browser.close()

        filename = f"{stock_symbol}_equity_analysis.pdf"
        return Response(
            pdf_bytes,
            status=200,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error generating PDF for {stock_symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/report/html/<stock_symbol>', methods=['GET'])
def get_report_html(stock_symbol):
    """Get analysis report as HTML."""
    try:
        stock_symbol = stock_symbol.upper()
        
        if stock_symbol not in analysis_results:
            return jsonify({
                'success': False,
                'error': 'No analysis results found'
            }), 404
        
        report = analysis_results[stock_symbol]
        
        if report.get('error'):
            return jsonify({
                'success': False,
                'error': report['error']
            }), 400
        
        # Generate HTML report
        html = _generate_html_report(report)
        
        return jsonify({
            'success': True,
            'html': html
        })
    except Exception as e:
        logger.error(f"Error generating HTML report: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _generate_html_report(report: dict) -> str:
    """Generate HTML representation of the report."""
    html = f"""
    <div class="report-container">
        <h1>{report['stock_symbol']} - Investment Analysis Report</h1>
        
        <section class="report-section">
            <h2>Executive Summary</h2>
            <div class="content">
                {_format_text(report['sections'].get('executive_summary', 'N/A'))}
            </div>
        </section>
        
        <section class="report-section">
            <h2>Financial Overview</h2>
            <div class="content">
                {_format_text(report['sections'].get('financial_overview', 'N/A'))}
            </div>
        </section>
        
        <section class="report-section">
            <h2>Growth Analysis</h2>
            <div class="content">
                {_format_text(report['sections'].get('growth_analysis', 'N/A'))}
            </div>
        </section>
        
        <section class="report-section">
            <h2>Financial Health</h2>
            <div class="content">
                {_format_text(report['sections'].get('financial_health', 'N/A'))}
            </div>
        </section>
        
        <section class="report-section">
            <h2>Quarterly Analysis</h2>
            <div class="content">
                {_format_text(report['sections'].get('quarterly_analysis', 'N/A'))}
            </div>
        </section>
        
        <section class="report-section">
            <h2>Investment Recommendation</h2>
            <div class="content recommendation">
                {_format_text(report['sections'].get('investment_recommendation', 'N/A'))}
            </div>
        </section>
    </div>
    """
    return html


def _format_text(text: str) -> str:
    """Format text for HTML display."""
    # Convert line breaks to HTML
    text = text.replace('\n', '<br>')
    # Wrap in paragraph tags if needed
    if text and not text.startswith('<'):
        text = f'<p>{text}</p>'
    return text


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'message': 'Stock Analysis API is running'
    })


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


if __name__ == '__main__':
    logger.info("Starting Stock Analysis API")
    app.run(debug=settings.debug, host='0.0.0.0', port=5000)
