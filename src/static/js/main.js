// Stock Analysis Report Generator - JavaScript

const API_BASE = '';

// DOM Elements
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

let currentStock = null;
let analysisInProgress = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadStocks();
    setupEventListeners();
});

function setupEventListeners() {
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
