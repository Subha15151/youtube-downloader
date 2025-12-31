// YouTube Downloader by Subha
document.addEventListener('DOMContentLoaded', function() {
    // Configuration
    const API_BASE_URL = 'http://localhost:5000/api';
    const APP_VERSION = '2.0';
    const APP_AUTHOR = 'Subha';
    
    // DOM Elements
    const videoUrlInput = document.getElementById('videoUrl');
    const fetchBtn = document.getElementById('fetchBtn');
    const resultsSection = document.getElementById('resultsSection');
    const videoCard = document.getElementById('videoCard');
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const errorMessage = document.getElementById('errorMessage');
    const retryBtn = document.getElementById('retryBtn');
    const formatTabs = document.getElementById('formatTabs');
    const formatsContainer = document.getElementById('formatsContainer');
    const bulkDownloadBtn = document.getElementById('bulkDownload');
    
    // State Management
    let currentVideoInfo = null;
    let currentFormats = {
        video: [],
        audio: []
    };
    let currentTab = 'video';
    
    // Initialize Application
    function init() {
        console.log(`🎬 YouTube Downloader v${APP_VERSION} by ${APP_AUTHOR}`);
        setupEventListeners();
        checkServerHealth();
        setupFormatTabs();
        setupInputValidation();
        displayWelcomeMessage();
    }
    
    // Setup Event Listeners
    function setupEventListeners() {
        fetchBtn.addEventListener('click', fetchVideoInfo);
        retryBtn.addEventListener('click', retryFetch);
        
        videoUrlInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                fetchVideoInfo();
            }
        });
        
        videoUrlInput.addEventListener('input', function() {
            if (this.value.trim()) {
                fetchBtn.disabled = false;
            } else {
                fetchBtn.disabled = false;
            }
        });
        
        bulkDownloadBtn.addEventListener('click', handleBulkDownload);
        
        // Add paste event for better UX
        videoUrlInput.addEventListener('paste', function(e) {
            setTimeout(() => {
                if (isValidYouTubeUrl(this.value)) {
                    this.style.borderColor = '#00C851';
                    setTimeout(() => {
                        this.style.borderColor = '';
                    }, 2000);
                }
            }, 10);
        });
    }
    
    // Setup Format Tabs
    function setupFormatTabs() {
        const tabs = formatTabs.querySelectorAll('.format-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', function() {
                // Update active tab
                tabs.forEach(t => t.classList.remove('active'));
                this.classList.add('active');
                
                // Update current tab
                currentTab = this.dataset.type;
                
                // Display formats for selected tab
                displayFormats(currentTab);
                
                // Add animation
                this.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    this.style.transform = '';
                }, 200);
            });
        });
    }
    
    // Setup Input Validation
    function setupInputValidation() {
        videoUrlInput.addEventListener('blur', function() {
            if (this.value.trim() && !isValidYouTubeUrl(this.value)) {
                showTooltip(this, 'Please enter a valid YouTube URL');
            }
        });
    }
    
    // Display Welcome Message
    function displayWelcomeMessage() {
        console.log('🚀 Application initialized successfully');
        console.log('👤 Owner:', APP_AUTHOR);
        console.log('📞 API Base:', API_BASE_URL);
        
        // Add subtle animation to logo
        const logo = document.querySelector('.logo');
        logo.classList.add('pulse');
        setTimeout(() => {
            logo.classList.remove('pulse');
        }, 2000);
    }
    
    // Fetch Video Information
    async function fetchVideoInfo() {
        const url = videoUrlInput.value.trim();
        
        // Validate input
        if (!url) {
            showError('Please enter a YouTube URL');
            videoUrlInput.focus();
            return;
        }
        
        if (!isValidYouTubeUrl(url)) {
            showError('Please enter a valid YouTube URL');
            videoUrlInput.focus();
            return;
        }
        
        // Show loading state
        showLoading();
        
        // Reset previous results
        resetResults();
        
        try {
            // Fetch video info from backend
            const response = await fetch(`${API_BASE_URL}/video-info?url=${encodeURIComponent(url)}`);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `Server error: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Store video info
            currentVideoInfo = data;
            
            // Process formats
            processFormats(data.formats || []);
            
            // Display video information
            displayVideoInfo(data);
            
            // Show success animation
            showSuccessAnimation();
            
            // Log success
            console.log('✅ Video info fetched successfully:', data.title);
            
        } catch (err) {
            console.error('❌ Error fetching video info:', err);
            showError(`Failed to fetch video information: ${err.message}`);
        } finally {
            hideLoading();
        }
    }
    
    // Process Formats
    function processFormats(formats) {
        currentFormats = {
            video: [],
            audio: []
        };
        
        if (!formats.length) {
            console.warn('⚠️ No formats available');
            return;
        }
        
        // Separate video and audio formats
        formats.forEach(format => {
            if (format.vcodec !== 'none') {
                // Video format
                currentFormats.video.push({
                    id: format.format_id || 'best',
                    quality: format.resolution || format.format_note || 'HD',
                    size: format.filesize || 0,
                    extension: format.ext || 'mp4',
                    type: 'video',
                    note: format.format_note || '',
                    isBest: format.format_note?.toLowerCase().includes('best') || false
                });
            } else if (format.acodec !== 'none') {
                // Audio format
                currentFormats.audio.push({
                    id: format.format_id || 'bestaudio',
                    quality: format.format_note || 'Audio',
                    size: format.filesize || 0,
                    extension: format.ext || 'mp3',
                    type: 'audio',
                    bitrate: format.format_note || '',
                    isBest: format.format_note?.toLowerCase().includes('best') || false
                });
            }
        });
        
        // Sort formats by quality/size
        currentFormats.video.sort((a, b) => {
            const qualityOrder = ['4K', '1440p', '1080p', '720p', '480p', '360p', '240p', '144p'];
            const aIndex = qualityOrder.indexOf(a.quality);
            const bIndex = qualityOrder.indexOf(b.quality);
            
            if (aIndex !== -1 && bIndex !== -1) return bIndex - aIndex;
            if (a.isBest) return -1;
            if (b.isBest) return 1;
            return b.size - a.size;
        });
        
        currentFormats.audio.sort((a, b) => b.size - a.size);
        
        console.log(`📊 Formats processed: ${currentFormats.video.length} video, ${currentFormats.audio.length} audio`);
    }
    
    // Display Video Information
    function displayVideoInfo(data) {
        // Update video details
        document.getElementById('videoTitle').textContent = data.title || 'Unknown Title';
        document.getElementById('videoChannel').textContent = data.channel || 'Unknown Channel';
        document.getElementById('videoDuration').textContent = data.duration || '00:00';
        document.getElementById('videoViews').textContent = data.view_count ? `${formatNumber(data.view_count)} views` : '0 views';
        document.getElementById('videoDescription').textContent = data.description || 'No description available';
        
        // Set thumbnail
        const thumbnail = document.getElementById('thumbnail');
        const videoId = data.video_id || extractYouTubeId(videoUrlInput.value);
        
        if (data.thumbnail) {
            thumbnail.src = data.thumbnail;
        } else if (videoId) {
            thumbnail.src = `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`;
        }
        
        // Fallback for thumbnail error
        thumbnail.onerror = function() {
            if (videoId) {
                this.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
            } else {
                this.src = 'https://via.placeholder.com/480x270/FF0000/FFFFFF?text=No+Thumbnail';
            }
        };
        
        // Update quality badge
        const qualityBadge = document.getElementById('qualityBadge');
        if (currentFormats.video.length > 0) {
            const bestQuality = currentFormats.video[0].quality;
            qualityBadge.innerHTML = `<i class="fas fa-check-circle"></i><span>${bestQuality} Available</span>`;
        }
        
        // Display formats for current tab
        displayFormats(currentTab);
        
        // Show results section
        resultsSection.style.display = 'block';
        
        // Scroll to results
        setTimeout(() => {
            resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 300);
    }
    
    // Display Formats
    function displayFormats(type) {
        const formats = currentFormats[type] || [];
        formatsContainer.innerHTML = '';
        
        if (formats.length === 0) {
            formatsContainer.innerHTML = `
                <div class="no-formats-message">
                    <i class="fas fa-exclamation-circle"></i>
                    <h4>No ${type} formats available</h4>
                    <p>Try selecting a different video or check the URL</p>
                </div>
            `;
            return;
        }
        
        // Display limited number of formats for better UX
        const displayFormats = formats.slice(0, 6);
        
        displayFormats.forEach((format, index) => {
            const formatCard = createFormatCard(format, index === 0);
            formatsContainer.appendChild(formatCard);
        });
        
        // Show format count
        const formatCount = document.createElement('div');
        formatCount.className = 'format-count';
        formatCount.textContent = `Showing ${displayFormats.length} of ${formats.length} formats`;
        formatsContainer.appendChild(formatCount);
    }
    
    // Create Format Card
    function createFormatCard(format, isBest = false) {
        const card = document.createElement('div');
        card.className = `format-option ${isBest ? 'premium' : ''}`;
        
        const icon = format.type === 'audio' ? 'fas fa-music' : 'fas fa-video';
        const typeText = format.type === 'audio' ? 'Audio' : 'Video';
        const sizeText = format.size > 0 ? formatBytes(format.size) : 'Size varies';
        
        card.innerHTML = `
            <div class="format-header">
                <div class="format-type">
                    <i class="${icon}"></i>
                    <h4>${typeText}</h4>
                </div>
                <div class="format-badge">${format.extension.toUpperCase()}</div>
            </div>
            <div class="format-quality">${format.quality}</div>
            <div class="format-details">
                <div class="format-size">${sizeText}</div>
                <div class="format-action">
                    <button class="download-btn" data-format="${format.id}">
                        <i class="fas fa-download"></i>
                        Download Now
                    </button>
                </div>
            </div>
        `;
        
        // Add click event
        const downloadBtn = card.querySelector('.download-btn');
        downloadBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            initiateDownload(format.id);
            
            // Add click effect
            downloadBtn.style.transform = 'scale(0.95)';
            setTimeout(() => {
                downloadBtn.style.transform = '';
            }, 200);
        });
        
        // Add hover effect to entire card
        card.addEventListener('click', () => {
            initiateDownload(format.id);
        });
        
        return card;
    }
    
    // Initiate Download
    async function initiateDownload(formatId) {
        const url = videoUrlInput.value.trim();
        
        if (!url || !currentVideoInfo) {
            showError('Please fetch video information first');
            return;
        }
        
        try {
            // Show download started notification
            showNotification('Download started', 'success');
            
            // Update button state
            const downloadBtns = document.querySelectorAll('.download-btn');
            downloadBtns.forEach(btn => {
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            });
            
            // Open download in new tab
            const downloadLink = `${API_BASE_URL}/download?url=${encodeURIComponent(url)}&format_id=${formatId}`;
            const newWindow = window.open(downloadLink, '_blank');
            
            // Check if popup was blocked
            if (!newWindow || newWindow.closed || typeof newWindow.closed === 'undefined') {
                showNotification('Popup blocked! Please allow popups for this site', 'warning');
                
                // Provide direct download link
                setTimeout(() => {
                    const directLink = document.createElement('a');
                    directLink.href = downloadLink;
                    directLink.download = `${currentVideoInfo.title}.${formatId.includes('audio') ? 'mp3' : 'mp4'}`;
                    directLink.click();
                }, 1000);
            }
            
            // Reset buttons after delay
            setTimeout(() => {
                downloadBtns.forEach(btn => {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-download"></i> Download Now';
                });
                showNotification('Download should start shortly', 'info');
            }, 3000);
            
            // Log download attempt
            console.log(`📥 Download initiated: ${formatId} for "${currentVideoInfo.title}"`);
            
        } catch (err) {
            console.error('❌ Download error:', err);
            showError(`Download failed: ${err.message}`);
        }
    }
    
    // Handle Bulk Download
    function handleBulkDownload() {
        if (!currentVideoInfo) {
            showError('Please fetch video information first');
            return;
        }
        
        showNotification('Bulk download feature coming soon!', 'info');
        
        // For now, initiate download of best video and audio
        if (currentFormats.video.length > 0) {
            initiateDownload(currentFormats.video[0].id);
        }
        if (currentFormats.audio.length > 0) {
            setTimeout(() => {
                initiateDownload(currentFormats.audio[0].id);
            }, 1000);
        }
    }
    
    // Retry Fetch
    function retryFetch() {
        hideError();
        fetchVideoInfo();
    }
    
    // Reset Results
    function resetResults() {
        currentVideoInfo = null;
        currentFormats = { video: [], audio: [] };
        resultsSection.style.display = 'none';
    }
    
    // Validation Functions
    function isValidYouTubeUrl(url) {
        const patterns = [
            /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$/,
            /^(https?:\/\/)?(www\.)?youtube\.com\/watch\?v=[\w-]+(&\S*)?$/,
            /^(https?:\/\/)?(www\.)?youtu\.be\/[\w-]+$/,
            /^(https?:\/\/)?(www\.)?youtube\.com\/shorts\/[\w-]+$/,
            /^(https?:\/\/)?(www\.)?youtube\.com\/playlist\?list=[\w-]+$/
        ];
        
        return patterns.some(pattern => pattern.test(url));
    }
    
    function extractYouTubeId(url) {
        const regExp = /^.*(youtu\.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=|\?v=)([^#&?]*).*/;
        const match = url.match(regExp);
        return (match && match[2].length === 11) ? match[2] : null;
    }
    
    // Helper Functions
    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0 || !bytes) return '0 Bytes';
        
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }
    
    function formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        }
        if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }
    
    // UI State Functions
    function showLoading() {
        loading.style.display = 'block';
        resultsSection.style.display = 'none';
        error.style.display = 'none';
        
        fetchBtn.disabled = true;
        fetchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        
        videoUrlInput.disabled = true;
    }
    
    function hideLoading() {
        loading.style.display = 'none';
        videoUrlInput.disabled = false;
        
        fetchBtn.disabled = false;
        fetchBtn.innerHTML = '<i class="fas fa-bolt"></i> Get Video';
    }
    
    function showError(message) {
        errorMessage.textContent = message;
        error.style.display = 'block';
        resultsSection.style.display = 'none';
        loading.style.display = 'none';
        
        // Add error animation
        error.style.animation = 'none';
        setTimeout(() => {
            error.style.animation = 'shake 0.5s ease';
        }, 10);
        
        console.error('❌ Error:', message);
    }
    
    function hideError() {
        error.style.display = 'none';
    }
    
    function showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
            <span>${message}</span>
        `;
        
        // Add to body
        document.body.appendChild(notification);
        
        // Show with animation
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
        
        // Remove after delay
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 3000);
        
        // Add notification styles if not already added
        if (!document.querySelector('#notification-styles')) {
            const styles = document.createElement('style');
            styles.id = 'notification-styles';
            styles.textContent = `
                .notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: #1a1a1a;
                    border-left: 4px solid #00C851;
                    padding: 15px 20px;
                    border-radius: 8px;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                    transform: translateX(120%);
                    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    z-index: 1000;
                    max-width: 350px;
                }
                .notification.show {
                    transform: translateX(0);
                }
                .notification-success {
                    border-left-color: #00C851;
                }
                .notification-warning {
                    border-left-color: #FFBB33;
                }
                .notification-info {
                    border-left-color: #00A8FF;
                }
                .notification i {
                    font-size: 1.2rem;
                }
                .notification-success i {
                    color: #00C851;
                }
                .notification-warning i {
                    color: #FFBB33;
                }
                .notification-info i {
                    color: #00A8FF;
                }
                .notification span {
                    color: white;
                    font-size: 0.95rem;
                }
            `;
            document.head.appendChild(styles);
        }
    }
    
    function showSuccessAnimation() {
        const fetchBtnIcon = fetchBtn.querySelector('i');
        fetchBtnIcon.className = 'fas fa-check';
        fetchBtn.style.background = 'linear-gradient(135deg, #00C851 0%, #007E33 100%)';
        
        setTimeout(() => {
            fetchBtnIcon.className = 'fas fa-bolt';
            fetchBtn.style.background = '';
        }, 2000);
    }
    
    function showTooltip(element, message) {
        // Remove existing tooltip
        const existingTooltip = document.querySelector('.tooltip');
        if (existingTooltip) existingTooltip.remove();
        
        // Create tooltip
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        tooltip.textContent = message;
        
        // Position tooltip
        const rect = element.getBoundingClientRect();
        tooltip.style.position = 'absolute';
        tooltip.style.top = `${rect.bottom + 5}px`;
        tooltip.style.left = `${rect.left}px`;
        
        document.body.appendChild(tooltip);
        
        // Remove after delay
        setTimeout(() => {
            tooltip.remove();
        }, 3000);
        
        // Add tooltip styles if not already added
        if (!document.querySelector('#tooltip-styles')) {
            const styles = document.createElement('style');
            styles.id = 'tooltip-styles';
            styles.textContent = `
                .tooltip {
                    background: #FF4444;
                    color: white;
                    padding: 8px 12px;
                    border-radius: 6px;
                    font-size: 0.9rem;
                    z-index: 1000;
                    animation: fadeIn 0.3s ease;
                    box-shadow: 0 3px 10px rgba(255, 68, 68, 0.3);
                }
                .tooltip::before {
                    content: '';
                    position: absolute;
                    top: -5px;
                    left: 20px;
                    width: 0;
                    height: 0;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-bottom: 5px solid #FF4444;
                }
            `;
            document.head.appendChild(styles);
        }
    }
    
    // Server Health Check
    async function checkServerHealth() {
        try {
            console.log('🔍 Checking server health...');
            const response = await fetch(`${API_BASE_URL}/health`);
            const data = await response.json();
            
            if (data.yt_dlp_available === false) {
                console.warn('⚠️ Server warning: yt-dlp might not be installed');
                showNotification('Server is running but yt-dlp might not be installed', 'warning');
            }
            
            console.log('✅ Server status:', data.status);
            
            // Show server status indicator
            const statusIndicator = document.createElement('div');
            statusIndicator.className = 'server-status-indicator';
            statusIndicator.innerHTML = `
                <i class="fas fa-server"></i>
                <span>Server: Online</span>
            `;
            document.querySelector('.owner-info').appendChild(statusIndicator);
            
            // Add status indicator styles
            const styles = document.createElement('style');
            styles.textContent = `
                .server-status-indicator {
                    background: rgba(0, 200, 81, 0.1);
                    border: 1px solid rgba(0, 200, 81, 0.3);
                    padding: 6px 12px;
                    border-radius: 50px;
                    font-size: 0.8rem;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    color: #00C851;
                    animation: pulse 2s infinite;
                }
            `;
            document.head.appendChild(styles);
            
        } catch (err) {
            console.warn('❌ Cannot connect to server. Make sure server.py is running.');
            
            // Show offline indicator
            const statusIndicator = document.createElement('div');
            statusIndicator.className = 'server-status-indicator offline';
            statusIndicator.innerHTML = `
                <i class="fas fa-server"></i>
                <span>Server: Offline</span>
            `;
            document.querySelector('.owner-info').appendChild(statusIndicator);
            
            // Update styles for offline state
            const styles = document.createElement('style');
            styles.textContent = `
                .server-status-indicator.offline {
                    background: rgba(255, 68, 68, 0.1);
                    border-color: rgba(255, 68, 68, 0.3);
                    color: #FF4444;
                }
            `;
            document.head.appendChild(styles);
            
            showNotification('Server is offline. Please start the backend server.', 'warning');
        }
    }
    
    // Initialize the application
    init();
    
    // Add global error handler
    window.addEventListener('error', function(e) {
        console.error('🌍 Global error:', e.error);
        showNotification('An unexpected error occurred', 'warning');
    });
    
    // Add beforeunload handler to clean up
    window.addEventListener('beforeunload', function() {
        console.log('👋 Application closing...');
    });
    
    // Export useful functions to global scope for debugging
    window.YTDownloader = {
        fetchVideoInfo,
        initiateDownload,
        isValidYouTubeUrl,
        extractYouTubeId,
        getCurrentVideo: () => currentVideoInfo,
        getFormats: () => currentFormats,
        version: APP_VERSION,
        author: APP_AUTHOR
    };
    
    console.log('✨ Application ready! Try pasting a YouTube URL.');
});