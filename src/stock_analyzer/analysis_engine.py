"""Stock analysis engine using LangGraph for reasoning and analysis workflow."""

import logging
import os
import pandas as pd
from pathlib import Path
from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from src.agents.llm_manager import LLMManager
from src.stock_analyzer.comprehensive_prompt_new import generate_comprehensive_html_report
from src.stock_analyzer.prompts import (
    STOCK_ANALYST_SYSTEM_PROMPT,
    COMPANY_OVERVIEW_PROMPT,
    QUANTITATIVE_ANALYSIS_PROMPT,
    QUALITATIVE_ANALYSIS_PROMPT,
    SHAREHOLDING_ANALYSIS_PROMPT,
    INVESTMENT_THESIS_PROMPT,
    VALUATION_AND_RECOMMENDATION_PROMPT,
    CONCLUSION_PROMPT,
)

logger = logging.getLogger(__name__)

# Response logging utility
def save_llm_response(stock_symbol: str, section_name: str, response_content: str):
    """Save LLM responses to files for debugging timeout issues."""
    try:
        response_dir = Path(__file__).parent.parent.parent / "llm_responses"
        response_dir.mkdir(exist_ok=True)
        
        # Create a file with stock name and section
        timestamp = Path(f"response_{Path(stock_symbol).name}_{section_name}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.txt")
        filepath = response_dir / timestamp
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Stock: {stock_symbol}\n")
            f.write(f"Section: {section_name}\n")
            f.write(f"Timestamp: {pd.Timestamp.now()}\n")
            f.write(f"Response Length: {len(response_content)} chars\n")
            f.write("="*80 + "\n\n")
            f.write(response_content)
        
        logger.info(f"Saved LLM response to {filepath}")
    except Exception as e:
        logger.warning(f"Could not save LLM response: {e}")

# Type definitions for LangGraph state
class AnalysisState(TypedDict):
    """State for comprehensive 7-section equity analysis workflow."""
    stock_symbol: str
    files_loaded: dict
    company_overview: str
    quantitative_analysis: str
    qualitative_analysis: str
    shareholding_analysis: str
    investment_thesis: str
    valuation_recommendation: str
    conclusion: str
    final_report: str
    error: str


class StockAnalysisEngine:
    """LangGraph-based stock analysis engine."""
    
    def __init__(self, stock_data_path: str = None, llm_provider: str = None, debug_mode: bool = False):
        """Initialize the analysis engine.
        
        Args:
            stock_data_path: Path to stock data folder. Defaults to static/stock-data or static if that doesn't exist
            llm_provider: Optional LLM provider ('openai' or 'claude'). Uses env var if not specified.
            debug_mode: If True, prints prompts but doesn't send to API
        """
        self.llm_manager = LLMManager(provider=llm_provider)
        self.llm = self.llm_manager.get_llm()
        self.debug_mode = debug_mode
        
        # Set stock data path - check new location first, then fall back to old location
        if stock_data_path:
            self.stock_data_path = Path(stock_data_path)
        else:
            new_location = Path(__file__).parent.parent.parent / "static" / "stock-data"
            old_location = Path(__file__).parent.parent.parent / "static"
            
            # Use new location if it has data, otherwise fall back to old
            if new_location.exists() and list(new_location.glob("*/")):
                self.stock_data_path = new_location
            else:
                self.stock_data_path = old_location
        
        self.graph = self._build_graph()
    
    def get_available_stocks(self):
        """Get list of available stocks from stock data folder."""
        stocks = []
        if self.stock_data_path.exists():
            for item in self.stock_data_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    stocks.append(item.name)
        return sorted(stocks)
    
    def load_stock_data(self, stock_symbol: str) -> dict:
        """Load CSV data for a stock.

        Keeps ALL metric rows (rows = metrics, columns = years).
        Trims to the last N year-columns to stay within token budget.
        """
        import re as _re

        stock_path = self.stock_data_path / stock_symbol
        data = {}

        if not stock_path.exists():
            raise ValueError(f"Stock {stock_symbol} data not found at {stock_path}")

        csv_files = {
            'balance_sheet':     ('balance_sheet.csv',          7),
            'cash_flow':         ('cash_flow.csv',              7),
            'growth_metrics':    ('growth_metrics.csv',         0),   # 0 = no year trimming (wide format)
            'key_metrics':       ('key_metrics.csv',            0),
            'profit_and_loss':   ('profit_and_loss_annual.csv', 7),
            'quarterly_results': ('quarterly_results.csv',      6),
            'ratios':            ('ratios.csv',                  7),
        }

        year_col_pattern = _re.compile(r'^((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|TTM|FY\d{2,4})$')

        for name, (filename, max_years) in csv_files.items():
            file_path = stock_path / filename
            if not file_path.exists():
                data[name] = f"{filename} not found"
                continue
            try:
                df = pd.read_csv(file_path)
                if max_years > 0:
                    # Identify year columns and keep only the most recent max_years
                    year_cols = [c for c in df.columns if year_col_pattern.match(str(c))]
                    other_cols = [c for c in df.columns if c not in year_cols]
                    recent_years = year_cols[-max_years:] if len(year_cols) > max_years else year_cols
                    keep = [c for c in other_cols if c.lower() != 'source'] + recent_years
                    df = df[[c for c in keep if c in df.columns]]
                else:
                    # Drop source column but keep everything else
                    df = df[[c for c in df.columns if c.lower() != 'source']]
                data[name] = df.to_string(index=False)
                logger.info(f"Loaded {name} for {stock_symbol}")
            except Exception as e:
                logger.warning(f"Failed to load {filename}: {e}")
                data[name] = f"Error loading {filename}"

        return data
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow for 7-section equity analysis."""
        graph = StateGraph(AnalysisState)
        
        # Add nodes for each analysis section
        graph.add_node("load_data", self._load_data_node)
        graph.add_node("company_overview", self._company_overview_node)
        graph.add_node("quantitative_analysis", self._quantitative_analysis_node)
        graph.add_node("qualitative_analysis", self._qualitative_analysis_node)
        graph.add_node("shareholding_analysis", self._shareholding_analysis_node)
        graph.add_node("investment_thesis", self._investment_thesis_node)
        graph.add_node("valuation_recommendation", self._valuation_recommendation_node)
        graph.add_node("conclusion", self._conclusion_node)
        graph.add_node("executive_summary", self._executive_summary_node)
        
        # Set up edges (workflow)
        graph.add_edge(START, "load_data")
        graph.add_edge("load_data", "company_overview")
        graph.add_edge("load_data", "quantitative_analysis")
        graph.add_edge("load_data", "qualitative_analysis")
        graph.add_edge("load_data", "shareholding_analysis")
        
        # All analyses must complete before investment thesis
        graph.add_edge("company_overview", "investment_thesis")
        graph.add_edge("quantitative_analysis", "investment_thesis")
        graph.add_edge("qualitative_analysis", "investment_thesis")
        graph.add_edge("shareholding_analysis", "investment_thesis")
        
        # Sequential: valuation after thesis
        graph.add_edge("investment_thesis", "valuation_recommendation")
        # Conclusion after valuation
        graph.add_edge("valuation_recommendation", "conclusion")
        # Final report generation
        graph.add_edge("conclusion", "executive_summary")
        graph.add_edge("executive_summary", END)
        
        return graph.compile()
    
    def _load_data_node(self, state: AnalysisState) -> dict:
        """Load stock data from CSV files."""
        try:
            logger.info(f"Loading data for {state['stock_symbol']}")
            files_data = self.load_stock_data(state['stock_symbol'])
            return {'files_loaded': files_data}
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return {'error': str(e)}
    
    def _company_overview_node(self, state: AnalysisState) -> dict:
        """Generate company overview section."""
        try:
            # Full data directly - don't truncate
            company_data = str(state['files_loaded'])
            
            prompt = COMPANY_OVERVIEW_PROMPT.format(
                stock_symbol=state['stock_symbol'],
                company_data=company_data
            )
            
            # DEBUG: Print prompt before sending
            print("\n" + "="*80)
            print("DEBUG: COMPANY OVERVIEW PROMPT")
            print("="*80)
            print(f"Stock Symbol: {state['stock_symbol']}")
            print(f"Data Available: {len(company_data)} chars")
            print("\nFormatted Prompt (first 2000 chars):")
            print(prompt[:2000])
            print("..."*20)
            print("="*80)
            
            if self.debug_mode:
                print("\n⚠️  DEBUG MODE: Stopping before API call")
                print("To continue, set debug_mode=False when initializing the engine\n")
                return {'company_overview': '[DEBUG MODE - PROMPT INSPECTION ONLY]'}
            
            response = self.llm.invoke([
                HumanMessage(content=STOCK_ANALYST_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            # Save response for debugging
            save_llm_response(state['stock_symbol'], 'company_overview', response.content)
            
            logger.info(f"Generated company overview for {state['stock_symbol']}")
            return {'company_overview': response.content}
        except Exception as e:
            logger.error(f"Error in company_overview_node: {e}")
            return {'company_overview': f"Error generating company overview: {str(e)}"}
    
    def _quantitative_analysis_node(self, state: AnalysisState) -> dict:
        """Generate quantitative analysis section."""
        try:
            # Pass full data without truncation
            quantitative_data = f"""
KEY METRICS:
{state['files_loaded'].get('key_metrics', 'Not available')}

BALANCE SHEET:
{state['files_loaded'].get('balance_sheet', 'Not available')}

CASH FLOW:
{state['files_loaded'].get('cash_flow', 'Not available')}

GROWTH METRICS:
{state['files_loaded'].get('growth_metrics', 'Not available')}

PROFIT & LOSS:
{state['files_loaded'].get('profit_and_loss', 'Not available')}

QUARTERLY RESULTS:
{state['files_loaded'].get('quarterly_results', 'Not available')}

RATIOS (ROCE%, Efficiency):
{state['files_loaded'].get('ratios', 'Not available')}
"""
            prompt = QUANTITATIVE_ANALYSIS_PROMPT.format(
                stock_symbol=state['stock_symbol'],
                quantitative_data=quantitative_data
            )
            
            # DEBUG: Print prompt before sending
            print("\n" + "="*80)
            print("DEBUG: QUANTITATIVE ANALYSIS PROMPT")
            print("="*80)
            print(f"Stock Symbol: {state['stock_symbol']}")
            print(f"Data Length: {len(quantitative_data)} chars")
            print("\nFormatted Prompt (first 2000 chars):")
            print(prompt[:2000])
            print("..."*20)
            print("="*80)
            
            if self.debug_mode:
                print("\n⚠️  DEBUG MODE: Stopping before API call\n")
                return {'quantitative_analysis': '[DEBUG MODE - PROMPT INSPECTION ONLY]'}
            
            response = self.llm.invoke([
                HumanMessage(content=STOCK_ANALYST_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            # Save response for debugging
            save_llm_response(state['stock_symbol'], 'quantitative_analysis', response.content)
            
            logger.info(f"Generated quantitative analysis for {state['stock_symbol']}")
            return {'quantitative_analysis': response.content}
        except Exception as e:
            logger.error(f"Error in quantitative_analysis_node: {e}")
            return {'quantitative_analysis': f"Error generating quantitative analysis: {str(e)}"}
    
    def _qualitative_analysis_node(self, state: AnalysisState) -> dict:
        """Generate qualitative analysis section."""
        try:
            qualitative_data = f"""
Stock: {state['stock_symbol']}
Sector: Based on NIFTY 50 listing

Available for Analysis:
- Financial performance trends from quantitative data
- Company stability indicators from balance sheet
- Growth profile from historical metrics

Context: Provide sector-level qualitative insights based on the company's financial performance indicators.
"""
            prompt = QUALITATIVE_ANALYSIS_PROMPT.format(
                stock_symbol=state['stock_symbol'],
                qualitative_data=qualitative_data
            )
            
            response = self.llm.invoke([
                HumanMessage(content=STOCK_ANALYST_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            # Save response for debugging
            save_llm_response(state['stock_symbol'], 'qualitative_analysis', response.content)
            
            logger.info(f"Generated qualitative analysis for {state['stock_symbol']}")
            return {'qualitative_analysis': response.content}
        except Exception as e:
            logger.error(f"Error in qualitative_analysis_node: {e}")
            return {'qualitative_analysis': f"Error generating qualitative analysis: {str(e)}"}
    
    def _shareholding_analysis_node(self, state: AnalysisState) -> dict:
        """Generate shareholding pattern analysis."""
        try:
            shareholding_data = f"""
Stock: {state['stock_symbol']}

Note: Detailed shareholding data (promoter holdings, FII/DII) may be available from the company's latest shareholding reports or regulatory filings.

Currently available data:
- Company financial metrics for overall company assessment
- Balance sheet data that may indicate capital structure
  
Analysis Point: Provide insights on what shareholding patterns typically mean for investor confidence and company stability.
"""
            prompt = SHAREHOLDING_ANALYSIS_PROMPT.format(
                stock_symbol=state['stock_symbol'],
                shareholding_data=shareholding_data
            )
            
            response = self.llm.invoke([
                HumanMessage(content=STOCK_ANALYST_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            # Save response for debugging
            save_llm_response(state['stock_symbol'], 'shareholding_analysis', response.content)
            
            logger.info(f"Generated shareholding analysis for {state['stock_symbol']}")
            return {'shareholding_analysis': response.content}
        except Exception as e:
            logger.error(f"Error in shareholding_analysis_node: {e}")
            return {'shareholding_analysis': f"Error generating shareholding analysis: {str(e)}"}
    
    def _investment_thesis_node(self, state: AnalysisState) -> dict:
        """Synthesize investment thesis from all analyses."""
        try:
            prompt = INVESTMENT_THESIS_PROMPT.format(
                stock_symbol=state['stock_symbol'],
                quantitative_summary=state.get('quantitative_analysis', 'Not available')[:1000],
                qualitative_summary=state.get('qualitative_analysis', 'Not available')[:1000],
                shareholding_summary=state.get('shareholding_analysis', 'Not available')[:500]
            )
            
            # DEBUG: Print prompt before sending
            print("\n" + "="*80)
            print("DEBUG: INVESTMENT THESIS PROMPT")
            print("="*80)
            print(f"Stock Symbol: {state['stock_symbol']}")
            print(f"Quantitative Summary Length: {len(state.get('quantitative_analysis', ''))} chars")
            print(f"Qualitative Summary Length: {len(state.get('qualitative_analysis', ''))} chars")
            print(f"Shareholding Summary Length: {len(state.get('shareholding_analysis', ''))} chars")
            print("\nFormatted Prompt (first 2000 chars):")
            print(prompt[:2000])
            print("..."*20)
            print("="*80)
            
            if self.debug_mode:
                print("\n⚠️  DEBUG MODE: Stopping before API call\n")
                return {'investment_thesis': '[DEBUG MODE - PROMPT INSPECTION ONLY]'}
            
            response = self.llm.invoke([
                HumanMessage(content=STOCK_ANALYST_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            # Save response for debugging
            save_llm_response(state['stock_symbol'], 'investment_thesis', response.content)
            
            logger.info(f"Generated investment thesis for {state['stock_symbol']}")
            return {'investment_thesis': response.content}
        except Exception as e:
            logger.error(f"Error in investment_thesis_node: {e}")
            return {'investment_thesis': f"Error generating investment thesis: {str(e)}"}
    
    def _valuation_recommendation_node(self, state: AnalysisState) -> dict:
        """Generate valuation and investment recommendation."""
        try:
            financial_summary = state.get('quantitative_analysis', 'Not available')[:500]
            market_data = state.get('company_overview', 'Not available')[:300]
            
            prompt = VALUATION_AND_RECOMMENDATION_PROMPT.format(
                stock_symbol=state['stock_symbol'],
                financial_summary=financial_summary,
                market_data=market_data
            )
            
            # DEBUG: Print prompt before sending
            print("\n" + "="*80)
            print("DEBUG: VALUATION AND RECOMMENDATION PROMPT")
            print("="*80)
            print(f"Stock Symbol: {state['stock_symbol']}")
            print(f"Financial Summary Length: {len(financial_summary)} chars")
            print(f"Market Data Length: {len(market_data)} chars")
            print("\nFormatted Prompt (first 2000 chars):")
            print(prompt[:2000])
            print("..."*20)
            print("="*80)
            
            if self.debug_mode:
                print("\n⚠️  DEBUG MODE: Stopping before API call\n")
                return {'valuation_recommendation': '[DEBUG MODE - PROMPT INSPECTION ONLY]'}
            
            response = self.llm.invoke([
                HumanMessage(content=STOCK_ANALYST_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            # Save response for debugging
            save_llm_response(state['stock_symbol'], 'valuation_recommendation', response.content)
            
            logger.info(f"Generated valuation & recommendation for {state['stock_symbol']}")
            return {'valuation_recommendation': response.content}
        except Exception as e:
            logger.error(f"Error in valuation_recommendation_node: {e}")
            return {'valuation_recommendation': f"Error generating valuation: {str(e)}"}
    
    def _conclusion_node(self, state: AnalysisState) -> dict:
        """Generate conclusion section."""
        try:
            full_analysis = f"""
Investment Thesis: {state.get('investment_thesis', 'Not available')[:300]}
Valuation: {state.get('valuation_recommendation', 'Not available')[:300]}
"""
            prompt = CONCLUSION_PROMPT.format(
                stock_symbol=state['stock_symbol'],
                full_analysis=full_analysis
            )
            
            response = self.llm.invoke([
                HumanMessage(content=STOCK_ANALYST_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            # Save response for debugging
            save_llm_response(state['stock_symbol'], 'conclusion', response.content)
            
            logger.info(f"Generated conclusion for {state['stock_symbol']}")
            return {'conclusion': response.content}
        except Exception as e:
            logger.error(f"Error in conclusion_node: {e}")
            return {'conclusion': f"Error generating conclusion: {str(e)}"}
    
    def _executive_summary_node(self, state: AnalysisState) -> dict:
        """Generate final professional HTML equity analysis report.
        
        This directly combines all 7 section outputs into complete HTML.
        No LLM call needed - just composition of existing detailed sections.
        """
        try:
            # Prepare analysis results
            analysis_results = {
                'company_overview': state.get('company_overview', ''),
                'quantitative_analysis': state.get('quantitative_analysis', ''),
                'qualitative_analysis': state.get('qualitative_analysis', ''),
                'shareholding_analysis': state.get('shareholding_analysis', ''),
                'investment_thesis': state.get('investment_thesis', ''),
                'valuation_recommendation': state.get('valuation_recommendation', ''),
                'conclusion': state.get('conclusion', '')
            }
            
            # Log section content lengths
            logger.info(f"Section content lengths: company_overview={len(analysis_results['company_overview'])}, quant={len(analysis_results['quantitative_analysis'])}, qual={len(analysis_results['qualitative_analysis'])}, shareholding={len(analysis_results['shareholding_analysis'])}, thesis={len(analysis_results['investment_thesis'])}, valuation={len(analysis_results['valuation_recommendation'])}, conclusion={len(analysis_results['conclusion'])}")
            
            # Generate complete HTML directly (no LLM call needed)
            html_report = generate_comprehensive_html_report(state['stock_symbol'], analysis_results)
            
            # Log report size
            logger.info(f"Generated complete HTML report: {len(html_report)} characters")
            if '<body>' in html_report and '</body>' in html_report:
                body_start = html_report.find('<body>')
                body_end = html_report.find('</body>')
                body_content = html_report[body_start+6:body_end]
                logger.info(f"HTML body content length: {len(body_content)} characters")
                if len(body_content.strip()) < 200:
                    logger.warning(f"WARNING: HTML body might be sparse! Content preview: {body_content[:300]}")
            
            # Save response for debugging
            save_llm_response(state['stock_symbol'], 'final_html_report', html_report)
            
            logger.info(f"Generated final HTML report for {state['stock_symbol']}")
            return {'final_report': html_report}
        except Exception as e:
            logger.error(f"Error generating final HTML report: {e}")
            return {'final_report': f"Error generating final report: {str(e)}"}
    
    def analyze_stock(self, stock_symbol: str) -> dict:
        """Run complete 7-section equity analysis using LangGraph workflow."""
        logger.info(f"Starting comprehensive analysis for {stock_symbol}")
        
        initial_state: AnalysisState = {
            'stock_symbol': stock_symbol,
            'files_loaded': {},
            'company_overview': '',
            'quantitative_analysis': '',
            'qualitative_analysis': '',
            'shareholding_analysis': '',
            'investment_thesis': '',
            'valuation_recommendation': '',
            'conclusion': '',
            'final_report': '',
            'error': ''
        }
        
        try:
            final_state = self.graph.invoke(initial_state)
            logger.info(f"Comprehensive analysis completed for {stock_symbol}")
            return final_state
        except Exception as e:
            logger.error(f"Analysis failed for {stock_symbol}: {e}")
            final_state = initial_state
            final_state['error'] = str(e)
            return final_state
    
    def get_analysis_report(self, stock_symbol: str) -> dict:
        """Get formatted equity analysis report with all 7 sections."""
        analysis = self.analyze_stock(stock_symbol)
        
        report = {
            'stock_symbol': stock_symbol,
            'company_overview': analysis.get('company_overview', 'Not available'),
            'quantitative_analysis': analysis.get('quantitative_analysis', 'Not available'),
            'qualitative_analysis': analysis.get('qualitative_analysis', 'Not available'),
            'shareholding_analysis': analysis.get('shareholding_analysis', 'Not available'),
            'investment_thesis': analysis.get('investment_thesis', 'Not available'),
            'valuation_recommendation': analysis.get('valuation_recommendation', 'Not available'),
            'conclusion': analysis.get('conclusion', 'Not available'),
            'final_report': analysis.get('final_report', 'Not available'),
            'error': analysis.get('error', '')
        }
        
        return report
