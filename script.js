document.addEventListener('DOMContentLoaded', () => {
    // ==========================================
    // 1. CONFIGURATION & STATE
    // ==========================================
    
    // ⚠️ IMPORTANT: Replace this URL with your Render URL after deployment!
    // Example: 'https://yt-downloader-api.onrender.com/api'
    const API_BASE_URL = 'http://127.0.0.1:5000/api'; 

    const state = {
        currentData: null,
        activeTab: 'video', // 'video' or 'audio'
        isLoading: false
    };

    // DOM Elements
    const elements = {
        inputUrl: document.getElementById('videoUrl'),
        fetchBtn: document.getElementById('fetchBtn'),
        loading: document.getElementById('loading'),
        results: document.getElementById('resultsSection'),
        error: document.getElementById('error'),
        errorMsg: document.getElementById('errorMessage'),
        retryBtn: document.getElementById('retryBtn'),
        formatsContainer: document.getElementById('formatsContainer'),
        videoCard: {
            title: document.getElementById('videoTitle'),
            thumb: document.getElementById('thumbnail'),
            duration: document.getElementById('videoDuration'),
            channel: document.getElementById('videoChannel'),
            views: document.getElementById('videoViews')
        },
        tabs: document.querySelectorAll('.tab-btn'),
        historySection: document.getElementById('historySection'),
        historyGrid: document.getElementById('historyGrid'),
        clearHistoryBtn: document.getElementById('clearHistory')
    };

    // ==========================================
    // 2. INITIALIZATION
    // ==========================================
    init();

    function init() {
        setupEventListeners();
        loadHistory();
        injectToastStyles(); // Ensures notifications look good
    }

    function setupEventListeners() {
        // Fetch Button
        elements.fetchBtn.addEventListener('click', handleFetch);

        // Enter Key in Input
        elements.inputUrl.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleFetch();
        });

        // Tab Switching (Video/Audio)
        elements.tabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                // Update UI classes
                elements.tabs.forEach(t => t.classList.remove('active'));
                e.currentTarget.classList.add('active');
                
                // Update State & Render
                state.activeTab = e.currentTarget.dataset.type;
                renderFormats();
            });
        });

        // Retry Button
        elements.retryBtn.addEventListener('click', () => {
            elements.error.style.display = 'none';
            handleFetch();
        });

        // Clear History
        elements.clearHistoryBtn.addEventListener('click', () => {
            localStorage.removeItem('yt_history');
            loadHistory();
            showToast('History cleared', 'success');
        });
    }

    // ==========================================
    // 3. CORE LOGIC (FETCH & RENDER)
    // ==========================================

    async function handleFetch() {
        const url = elements.inputUrl.value.trim();

        if (!isValidUrl(url)) {
            showToast('Please enter a valid YouTube URL', 'error');
            return;
        }

        setLoading(true);
        resetUI();

        try {
            // Call the Backend
            const response = await fetch(`${API_BASE_URL}/video-info?url=${encodeURIComponent(url)}`);
            const data = await response.json();

            if (!data.success) throw new Error(data.error || 'Failed to fetch video');

            // Success
            state.currentData = data;
            updateVideoCard(data);
            renderFormats();
            addToHistory(data);
            
            elements.results.style.display = 'block';
            showToast('Video fetched successfully!', 'success');

        } catch (error) {
            console.error(error);
            elements.error.style.display = 'flex';
            elements.errorMsg.textContent = error.message;
        } finally {
            setLoading(false);
        }
    }

    function updateVideoCard(data) {
        elements.videoCard.title.textContent = data.title;
        elements.videoCard.channel.textContent = data.channel;
        elements.videoCard.views.textContent = formatNumber(data.view_count) + ' views';
        elements.videoCard.duration.textContent = data.duration;
        elements.videoCard.thumb.src = data.thumbnail;
        
        // Use high-res thumbnail if available
        if(data.video_id) {
             elements.videoCard.thumb.src = `https://img.youtube.com/vi/${data.video_id}/maxresdefault.jpg`;
        }
    }

    function renderFormats() {
        if (!state.currentData) return;

        elements.formatsContainer.innerHTML = '';
        const formats = state.currentData.formats || [];

        // Filter formats based on active tab
        const filteredFormats = formats.filter(f => {
            if (state.activeTab === 'audio') {
                return f.acodec !== 'none' && f.vcodec === 'none'; // Audio only
            } else {
                return f.vcodec !== 'none'; // Video (may contain audio or not)
            }
        });

        if (filteredFormats.length === 0) {
            elements.formatsContainer.innerHTML = '<div class="format-item">No formats found for this type.</div>';
            return;
        }

        // Generate HTML for each format
        filteredFormats.forEach(format => {
            const isVideo = state.activeTab === 'video';
            const quality = isVideo ? (format.resolution || format.quality + 'p') : 'Audio';
            const size = format.filesize ? formatBytes(format.filesize) : 'Unknown size';
            const ext = format.ext.toUpperCase();
            
            const div = document.createElement('div');
            div.className = 'format-item';
            div.innerHTML = `
                <div class="format-info">
                    <b>${quality} <span class="badge">${ext}</span></b>
                    <span>${size} • ${format.note || 'Standard'}</span>
                </div>
                <button class="dwn-btn" onclick="downloadFile('${state.currentData.original_url}', '${format.format_id}')">
                    <i class="fas fa-download"></i> Download
                </button>
            `;
            elements.formatsContainer.appendChild(div);
        });
    }

    // Global function for the onclick event in HTML string above
    window.downloadFile = (videoUrl, formatId) => {
        showToast('Starting download...', 'success');
        const downloadLink = `${API_BASE_URL}/download?url=${encodeURIComponent(videoUrl)}&format_id=${formatId}`;
        window.location.href = downloadLink;
    };

    // ==========================================
    // 4. HISTORY & UTILS
    // ==========================================

    function addToHistory(data) {
        let history = JSON.parse(localStorage.getItem('yt_history') || '[]');
        
        // Avoid duplicates
        history = history.filter(h => h.id !== data.video_id);
        
        // Add new item to top
        history.unshift({
            id: data.video_id,
            title: data.title,
            thumb: data.thumbnail,
            timestamp: new Date().getTime()
        });

        // Limit to 4 items
        if (history.length > 4) history.pop();

        localStorage.setItem('yt_history', JSON.stringify(history));
        loadHistory();
    }

    function loadHistory() {
        const history = JSON.parse(localStorage.getItem('yt_history') || '[]');
        
        if (history.length === 0) {
            elements.historySection.style.display = 'none';
            return;
        }

        elements.historySection.style.display = 'block';
        elements.historyGrid.innerHTML = '';

        history.forEach(item => {
            const div = document.createElement('div');
            div.className = 'history-item';
            // Simple inline style for history items since we didn't add it to main CSS
            div.style.cssText = `
                background: rgba(255,255,255,0.05); 
                padding: 10px; 
                border-radius: 8px; 
                display: flex; 
                gap: 10px; 
                align-items: center; 
                cursor: pointer;
                transition: 0.2s;
            `;
            div.onmouseover = () => div.style.background = 'rgba(255,255,255,0.1)';
            div.onmouseout = () => div.style.background = 'rgba(255,255,255,0.05)';
            
            div.innerHTML = `
                <img src="${item.thumb}" style="width: 60px; height: 34px; object-fit: cover; border-radius: 4px;">
                <div style="overflow: hidden;">
                    <h4 style="font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: white;">${item.title}</h4>
                </div>
            `;
            
            // Click to reload this video
            div.onclick = () => {
                elements.inputUrl.value = `https://youtube.com/watch?v=${item.id}`;
                handleFetch();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            };
            
            elements.historyGrid.appendChild(div);
        });
    }

    // Toast Notification System
    function showToast(msg, type = 'info') {
        const container = document.getElementById('notification-container');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        // Icons based on type
        const icon = type === 'success' ? 'check-circle' : 'exclamation-circle';
        
        toast.innerHTML = `<i class="fas fa-${icon}"></i> ${msg}`;
        container.appendChild(toast);

        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 10);

        // Remove after 3s
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // Helper: Validations & Formatting
    function isValidUrl(string) {
        try {
            const url = new URL(string);
            return url.hostname.includes('youtube.com') || url.hostname.includes('youtu.be');
        } catch (_) {
            return false;
        }
    }

    function formatNumber(num) {
        return new Intl.NumberFormat('en-US', { notation: "compact", compactDisplay: "short" }).format(num);
    }

    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
    }

    function setLoading(bool) {
        state.isLoading = bool;
        elements.loading.style.display = bool ? 'block' : 'none';
        elements.fetchBtn.disabled = bool;
        elements.fetchBtn.innerHTML = bool ? '<span>Processing...</span>' : '<span>Fetch Video</span> <i class="fas fa-arrow-right"></i>';
    }

    function resetUI() {
        elements.results.style.display = 'none';
        elements.error.style.display = 'none';
    }

    // Inject CSS for Toasts (Dynamic)
    function injectToastStyles() {
        const style = document.createElement('style');
        style.textContent = `
            #notification-container {
                position: fixed; top: 20px; right: 20px; z-index: 9999;
                display: flex; flex-direction: column; gap: 10px;
            }
            .toast {
                background: #1f1f1f; color: white; padding: 12px 20px;
                border-radius: 8px; border-left: 4px solid #00C851;
                box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                display: flex; align-items: center; gap: 10px;
                transform: translateX(120%); transition: transform 0.3s cubic-bezier(0.68, -0.55, 0.27, 1.55);
                font-size: 0.9rem;
            }
            .toast.show { transform: translateX(0); }
            .toast-error { border-left-color: #ff4444; }
            .toast i { font-size: 1.1rem; }
            .toast-success i { color: #00C851; }
            .toast-error i { color: #ff4444; }
            
            .history-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; margin-top: 15px; }
            .clear-history-btn { background: transparent; border: 1px solid rgba(255,255,255,0.1); color: #aaa; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
            .clear-history-btn:hover { color: white; border-color: white; }
            .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
            .badge { background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; margin-left: 5px; }
        `;
        document.head.appendChild(style);
    }
});