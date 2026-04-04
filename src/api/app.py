"""Flask API for stock analysis service."""

import logging
import json
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import threading
from playwright.sync_api import sync_playwright
from src.analysis import StockAnalysisEngine
from src.chat import StockAnalysisChat, MultiStockChat
from src.common import settings

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

# Initialize chat interfaces
# - Single stock analysis chat
chat_interface = StockAnalysisChat()

# - Multi-stock chat (uses screener embeddings + analysis embeddings)
multi_stock_chat = MultiStockChat(llm_provider=settings.llm_provider)

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


# ============================================================
# CHAT API ENDPOINTS - Ask questions about analyzed stocks
# ============================================================

@app.route('/api/chat/ask', methods=['POST'])
def chat_ask():
    """Ask a question about a specific stock's analysis.
    
    Request body:
    {
        "stock_symbol": "ASIANPAINT",
        "question": "What is the best price to buy?"
    }
    """
    try:
        data = request.json
        stock_symbol = data.get('stock_symbol', '').upper()
        question = data.get('question', '').strip()
        
        if not stock_symbol or not question:
            return jsonify({
                'success': False,
                'error': 'stock_symbol and question are required'
            }), 400
        
        # Check if stock has been analyzed
        if stock_symbol not in analysis_results:
            return jsonify({
                'success': False,
                'error': f'No analysis found for {stock_symbol}. Please analyze the stock first.'
            }), 404
        
        # Ask question using chat interface
        try:
            result = chat_interface.answer_question(question, stock_symbol)
            
            return jsonify({
                'success': True,
                'stock_symbol': stock_symbol,
                'question': question,
                'answer': result.get('answer', ''),
                'confidence': result.get('confidence', 0),
                'sources': result.get('sources', [])
            })
        except Exception as e:
            logger.warning(f"Chat error for {stock_symbol}: {e}")
            return jsonify({
                'success': False,
                'error': f'Could not answer question: {str(e)}'
            }), 500
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/chat/search', methods=['POST'])
def chat_search():
    """Search across multiple stocks' analyses.
    
    Request body:
    {
        "query": "stocks with P/E greater than 30",
        "symbols": ["ASIANPAINT", "TCS", "INFY"]
    }
    """
    try:
        data = request.json
        query = data.get('query', '').strip()
        symbols = data.get('symbols', [])
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'query is required'
            }), 400
        
        # Use all analyzed symbols if none specified
        if not symbols:
            symbols = list(analysis_results.keys())
        
        if not symbols:
            return jsonify({
                'success': False,
                'error': 'No stocks have been analyzed yet'
            }), 404
        
        # Filter to only analyzed stocks
        symbols = [s.upper() for s in symbols if s.upper() in analysis_results]
        
        if not symbols:
            return jsonify({
                'success': False,
                'error': f'None of the specified stocks have been analyzed'
            }), 404
        
        # Perform multi-stock search
        try:
            results = chat_interface.multi_stock_search(query, symbols=symbols)
            
            return jsonify({
                'success': True,
                'query': query,
                'stocks_searched': symbols,
                'results': results
            })
        except Exception as e:
            logger.warning(f"Multi-stock search error: {e}")
            return jsonify({
                'success': False,
                'error': f'Search failed: {str(e)}'
            }), 500
    
    except Exception as e:
        logger.error(f"Error in search endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/chat/compare', methods=['POST'])
def chat_compare():
    """Compare multiple stocks based on analysis.
    
    Request body:
    {
        "question": "Which stock has better growth?",
        "symbols": ["ASIANPAINT", "TCS"]
    }
    """
    try:
        data = request.json
        question = data.get('question', '').strip()
        symbols = data.get('symbols', [])
        
        if not question or not symbols:
            return jsonify({
                'success': False,
                'error': 'question and symbols are required'
            }), 400
        
        # Filter to only analyzed stocks
        symbols = [s.upper() for s in symbols if s.upper() in analysis_results]
        
        if not symbols:
            return jsonify({
                'success': False,
                'error': f'None of the specified stocks have been analyzed'
            }), 404
        
        if len(symbols) < 2:
            return jsonify({
                'success': False,
                'error': 'At least 2 analyzed stocks required for comparison'
            }), 400
        
        # Get comparative answer
        try:
            result = chat_interface.get_comparative_answer(question, symbols)
            
            return jsonify({
                'success': True,
                'question': question,
                'stocks': symbols,
                'comparison': result.get('answer', ''),
                'confidence': result.get('confidence', 0)
            })
        except Exception as e:
            logger.warning(f"Comparison error: {e}")
            return jsonify({
                'success': False,
                'error': f'Comparison failed: {str(e)}'
            }), 500
    
    except Exception as e:
        logger.error(f"Error in compare endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================
# MULTI-STOCK CHAT API ENDPOINTS (Screener + Analysis)
# ============================================================

@app.route('/api/chat/multi-query', methods=['POST'])
def multi_stock_query():
    """Query across multiple stocks using screener data and analysis.
    
    This endpoint handles:
    1. Cross-stock financial queries (e.g., "stocks with P/E < 20")
    2. Single stock analysis queries (e.g., "analyze ASIANPAINT")
    3. Comparison queries (e.g., "compare INFY and TCS")
    
    Request body:
    {
        "query": "Which stocks have price less than 200?",
        "stocks": ["ASIANPAINT", "TCS"],  # Optional - if specified, limits search
        "single_stock": "ASIANPAINT"       # Optional - for analysis queries
    }
    """
    try:
        data = request.json
        query = data.get('query', '').strip()
        stocks = data.get('stocks', [])
        single_stock = data.get('single_stock', '').upper() if data.get('single_stock') else None
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'query is required'
            }), 400
        
        # Use multi-stock chat to answer
        result = multi_stock_chat.answer_question(
            query=query,
            stock=single_stock,
            stocks=stocks if stocks else None
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'query_type': result.get('query_type'),
            'answer': result.get('answer'),
            'sources': result.get('sources', []),
            'confidence': result.get('confidence', 0)
        })
        
    except Exception as e:
        logger.error(f"Error in multi-stock query: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/chat/screener-query', methods=['POST'])
def screener_query():
    """Query screener data across all stocks.
    
    Request body:
    {
        "query": "stocks with price < 200",
        "stocks": ["ASIANPAINT", "TCS"]  # Optional
    }
    """
    try:
        data = request.json
        query = data.get('query', '').strip()
        stocks = data.get('stocks', [])
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'query is required'
            }), 400
        
        # Use screener chat
        result = multi_stock_chat.answer_screener_query(
            query=query,
            stocks=stocks if stocks else None,
            top_k=10
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'answer': result.get('answer'),
            'sources': result.get('sources', []),
            'confidence': result.get('confidence', 0)
        })
        
    except Exception as e:
        logger.error(f"Error in screener query: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/embeddings/embed-screener-data', methods=['POST'])
def embed_screener_data():
    """Embed all screener CSV data for cross-stock search.
    
    This endpoint triggers embedding of all stock CSV data.
    Run this after pulling screener data.
    """
    try:
        logger.info("Starting screener data embedding...")
        
        from src.utils.screener_embedding_store import ScreenerEmbeddingStore
        
        store = ScreenerEmbeddingStore()
        results = store.embed_all_stocks()
        
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        return jsonify({
            'success': True,
            'message': f'Embedded {success_count}/{total_count} stocks',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error embedding screener data: {e}")
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
