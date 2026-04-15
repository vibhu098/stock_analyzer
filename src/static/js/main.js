// Stock Analysis Report Generator - JavaScript

const API_BASE = '';

// ============================================================
// ANALYSIS FEATURE - DOM Elements
// ============================================================
const stockSelect = document.getElementById('stockSelect');
const analyzeBtn = document.getElementById('analyzeBtn');
const resetBtn = document.getElementById('resetBtn');
const exportBtn = document.getElementById('exportBtn');
const statusIndicator = document.getElementById('statusIndicator');
const statusMessage = document.getElementById('statusMessage');
const progressFill = document.getElementById('progressFill');
const reportPanel = document.getElementById('reportPanel');
const reportContent = document.getElementById('reportContent');
const emptyState = document.getElementById('emptyState');
const stockInfo = document.getElementById('stockInfo');
const selectedStockName = document.getElementById('selectedStockName');
const reportStock = document.getElementById('reportStock');
const generatedTime = document.getElementById('generatedTime');
const reportTitle = document.getElementById('reportTitle');

// ============================================================
// CHAT FEATURE - DOM Elements (Independent)
// ============================================================
const chatPanel = document.getElementById('chatPanel');
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const chatSendBtn = document.getElementById('chatSendBtn');

// State
let currentStock = null;
let analysisInProgress = false;
let chatHistory = [];
let availableStocks = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('✓ DOMContentLoaded fired - initializing app');
    loadStocks();
    setupAnalysisEventListeners();
    setupChatEventListeners();
    setupTabEventListeners();
    console.log('✓ All setup functions called');
});

// ============================================================
// ANALYSIS FEATURE
// ============================================================

function setupAnalysisEventListeners() {
    stockSelect.addEventListener('change', onStockSelected);
    analyzeBtn.addEventListener('click', startAnalysis);
    resetBtn.addEventListener('click', resetSelection);
    exportBtn.addEventListener('click', exportPDF);
}

async function loadStocks() {
    try {
        const response = await fetch(`${API_BASE}/api/stocks`);
        const data = await response.json();

        if (data.success) {
            const stocks = data.stocks;
            availableStocks = stocks;
            
            // Populate analysis stock selector
            stocks.forEach(stock => {
                const option = document.createElement('option');
                option.value = stock;
                option.textContent = stock;
                stockSelect.appendChild(option);
            });
        } else {
            showNotification('Failed to load stocks', 'error');
        }
    } catch (error) {
        console.error('Error loading stocks:', error);
        showNotification('Error loading stocks', 'error');
    }
}

function onStockSelected() {
    if (stockSelect.value) {
        analyzeBtn.disabled = false;
        currentStock = stockSelect.value;
    } else {
        analyzeBtn.disabled = true;
        currentStock = null;
    }
}

async function startAnalysis() {
    if (!currentStock) {
        showNotification('Please select a stock', 'error');
        return;
    }

    if (analysisInProgress) {
        return;
    }

    analysisInProgress = true;
    analyzeBtn.disabled = true;
    stockSelect.disabled = true;

    // Show status
    statusIndicator.classList.add('active');
    statusIndicator.classList.remove('success', 'error');
    statusIndicator.classList.add('processing');
    statusMessage.textContent = 'Starting analysis...';
    progressFill.style.width = '10%';

    try {
        // Trigger analysis
        const response = await fetch(`${API_BASE}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ stock_symbol: currentStock })
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to start analysis');
        }

        // Poll for results
        await pollAnalysisStatus();
    } catch (error) {
        console.error('Error starting analysis:', error);
        showStatus('error', `Error: ${error.message}`);
        analysisInProgress = false;
        analyzeBtn.disabled = false;
        stockSelect.disabled = false;
    }
}

async function pollAnalysisStatus() {
    const maxAttempts = 600; // 20 minutes max (600 attempts × 2 sec each = 1200 sec = 20 min)
    let attempts = 0;

    while (attempts < maxAttempts && analysisInProgress) {
        try {
            const response = await fetch(`${API_BASE}/api/status/${currentStock}`);
            const data = await response.json();

            if (data.success) {
                const status = data.status;
                const progress = status.progress || 0;

                // Update progress
                progressFill.style.width = progress + '%';
                statusMessage.textContent = status.message;

                if (status.status === 'completed') {
                    showStatus('success', 'Analysis completed! ✓');
                    await loadAnalysisResults();
                    analysisInProgress = false;
                    break;
                } else if (status.status === 'error') {
                    showStatus('error', status.message);
                    analysisInProgress = false;
                    analyzeBtn.disabled = false;
                    stockSelect.disabled = false;
                    break;
                }
            }
        } catch (error) {
            console.error('Error polling status:', error);
        }

        // Wait before next poll
        await new Promise(resolve => setTimeout(resolve, 2000));
        attempts++;
    }

    if (attempts >= maxAttempts) {
        showStatus('error', 'Analysis timeout - took longer than 20 minutes');
        analysisInProgress = false;
        analyzeBtn.disabled = false;
        stockSelect.disabled = false;
    }
}

async function loadAnalysisResults() {
    try {
        const response = await fetch(`${API_BASE}/api/results/${currentStock}`);
        const data = await response.json();

        if (data.success) {
            const report = data.report;
            displayReport(report);
            showNotification('Analysis complete!', 'success');
        } else {
            throw new Error(data.error || 'Failed to load results');
        }
    } catch (error) {
        console.error('Error loading results:', error);
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        analysisInProgress = false;
        analyzeBtn.disabled = false;
        stockSelect.disabled = false;
    }
}

function displayReport(report) {
    // Update metadata
    reportTitle.textContent = `${currentStock} - Investment Analysis Report`;
    reportStock.textContent = currentStock;
    generatedTime.textContent = new Date().toLocaleString();

    // Check if this is the new HTML report format
    if (report.final_report && report.final_report.includes('<!DOCTYPE')) {
        // Display as HTML iframe embed
        const iframeId = `report-iframe-${Date.now()}`;
        const htmlContent = report.final_report;
        
        reportContent.innerHTML = `
            <div style="width: 100%; height: 100%; overflow: auto;">
                <iframe 
                    id="${iframeId}" 
                    style="width: 100%; height: 800px; border: none; border-radius: 8px;"
                    sandbox="allow-same-origin"
                ></iframe>
            </div>
        `;
        
        const iframe = document.getElementById(iframeId);
        iframe.contentDocument.open();
        iframe.contentDocument.write(htmlContent);
        iframe.contentDocument.close();
    } else {
        // Fallback to old section-based format
        let html = '';
        const sections = report.sections || {};

        const sectionOrder = [
            { key: 'company_overview', title: 'Company Overview' },
            { key: 'quantitative_analysis', title: 'Quantitative Analysis' },
            { key: 'qualitative_analysis', title: 'Qualitative Analysis' },
            { key: 'shareholding_analysis', title: 'Shareholding Pattern' },
            { key: 'investment_thesis', title: 'Investment Thesis' },
            { key: 'valuation_recommendation', title: 'Valuation & Recommendation' },
            { key: 'conclusion', title: 'Conclusion' }
        ];

        sectionOrder.forEach(({ key, title }) => {
            if (report[key]) {
                const content = report[key];
                html += `
                    <div class="report-section">
                        <h3>${title}</h3>
                        <div class="content">
                            ${content.replace(/\n/g, '<br>')}
                        </div>
                    </div>
                `;
            }
        });

        if (!html) {
            html = '<p>No report data available</p>';
        }

        reportContent.innerHTML = html;
    }

    // Show report panel
    emptyState.style.display = 'none';
    reportPanel.classList.add('active');
    stockInfo.style.display = 'block';
    selectedStockName.textContent = currentStock;
    resetBtn.style.display = 'block';
    exportBtn.style.display = 'block';
}

function showStatus(type, message) {
    statusIndicator.classList.remove('processing', 'success', 'error');
    statusIndicator.classList.add(type, 'active');
    statusMessage.textContent = message;

    if (type === 'success') {
        setTimeout(() => {
            statusIndicator.classList.remove('active');
        }, 3000);
    }
}

function resetSelection() {
    stockSelect.value = '';
    analyzeBtn.disabled = true;
    resetBtn.style.display = 'none';
    exportBtn.style.display = 'none';
    stockInfo.style.display = 'none';
    reportPanel.classList.remove('active');
    emptyState.style.display = 'block';
    reportContent.innerHTML = '';
    statusIndicator.classList.remove('active');
    currentStock = null;
}

function exportPDF() {
    if (!currentStock) {
        showNotification('No stock selected.', 'error');
        return;
    }
    showNotification('Generating PDF, please wait…', 'success');
    window.location.href = `/report/${encodeURIComponent(currentStock)}/pdf`;
}

function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 4000);
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ============================================================
// INDEPENDENT CHAT FEATURE
// ============================================================

function setupChatEventListeners() {
    // Chat message sending
    chatSendBtn.addEventListener('click', sendChatMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });
    
    // Enable chat input by default
    chatInput.disabled = false;
    chatSendBtn.disabled = false;
    
    // Show welcome message
    addChatMessage('assistant', 
        '👋 Welcome! Ask me anything about Indian stocks. Examples:\n' +
        '• "Tell me about ASIANPAINT"\n' +
        '• "Which stocks have P/E < 20?"\n' +
        '• "Compare INFY vs TCS"\n' +
        '• "Stocks with highest ROE"\n\n' +
        'I\'ll automatically search relevant stocks based on your question.',
        0.95
    );
}

/**
 * Setup tab navigation event listeners
 * Handles switching between Analysis and Chat tabs
 */
function setupTabEventListeners() {
    console.log('🔧 Setting up tab event listeners...');
    
    const tabBtns = document.querySelectorAll('.tab-btn');
    console.log(`Found ${tabBtns.length} tab buttons`);
    
    tabBtns.forEach((btn) => {
        btn.addEventListener('click', function(e) {
            console.log('Tab button clicked!');
            
            const tabName = btn.getAttribute('data-tab');
            console.log(`Switching to tab: ${tabName}`);
            
            // Remove active class from all tabs and buttons
            document.querySelectorAll('.tab-btn').forEach(function(b) {
                b.classList.remove('active');
            });
            
            document.querySelectorAll('.tab-content').forEach(function(content) {
                content.classList.remove('active');
            });
            
            // Add active class to clicked button and corresponding tab
            btn.classList.add('active');
            console.log(`✓ Added .active to button`);
            
            const activeTab = document.getElementById(tabName);
            if (activeTab) {
                activeTab.classList.add('active');
                console.log(`✓ Tab ${tabName} activated - display should be flex now`);
            } else {
                console.error(`ERROR: Could not find tab element with id: ${tabName}`);
            }
        });
    });
    
    console.log('✓ Tab event listeners setup complete');
}

/**
 * Extract stock symbols from user query
 * Looks for patterns like "INFY", "TCS", or common stock names
 */
function extractStocksFromQuery(query, availableStocks) {
    const queryUpper = query.toUpperCase();
    const found = [];
    
    // Find all exact matches for available stocks
    availableStocks.forEach(stock => {
        if (queryUpper.includes(stock)) {
            found.push(stock);
        }
    });
    
    // Remove duplicates while preserving order
    return [...new Set(found)];
}

function addChatMessage(sender, text, confidence = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}`;

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    
    // For assistant messages, render markdown; for user messages, escape and preserve text
    if (sender === 'assistant') {
        // Render markdown for assistant responses
        bubble.innerHTML = marked.parse(text);
        // Add markdown class for styling
        bubble.classList.add('markdown-content');
    } else {
        // User messages: escape HTML but preserve formatting
        bubble.innerHTML = escapeHtml(text).replace(/\n/g, '<br>');
    }

    if (sender === 'assistant' && confidence !== null) {
        const confDiv = document.createElement('div');
        confDiv.className = 'chat-confidence';
        confDiv.textContent = `Confidence: ${(confidence * 100).toFixed(0)}%`;
        bubble.appendChild(confDiv);
    }

    messageDiv.appendChild(bubble);
    chatMessages.appendChild(messageDiv);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message assistant';
    messageDiv.id = 'loading-message';

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chat-loading';
    loadingDiv.innerHTML = `<span>Thinking</span><div class="chat-loading-dots">
        <span></span><span></span><span></span>
    </div>`;

    messageDiv.appendChild(loadingDiv);
    chatMessages.appendChild(messageDiv);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeLoadingMessage() {
    const loadingMsg = document.getElementById('loading-message');
    if (loadingMsg) {
        loadingMsg.remove();
    }
}

async function sendChatMessage() {
    const question = chatInput.value.trim();

    if (!question) {
        return;
    }

    // Add user message
    addChatMessage('user', question);
    chatInput.value = '';
    chatInput.disabled = true;
    chatSendBtn.disabled = true;

    // Show loading state
    addLoadingMessage();

    try {
        // Use unified chat endpoint - it handles both single and multi-stock queries
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: question
            })
        });

        const data = await response.json();
        removeLoadingMessage();

        if (data.success) {
            addChatMessage('assistant', data.answer, data.confidence);
        } else {
            addChatMessage('assistant', `Sorry, I couldn't answer that. ${data.error || 'Please try again.'}`);
        }
    } catch (error) {
        console.error('Chat error:', error);
        removeLoadingMessage();
        addChatMessage('assistant', `Error: ${error.message}. Please try again.`);
    } finally {
        chatInput.disabled = false;
        chatSendBtn.disabled = false;
        chatInput.focus();
    }
}

