from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import os
import json
import tempfile
import shutil
import logging
from datetime import datetime
from urllib.parse import urlparse, unquote

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('youtube_downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Check if yt-dlp is installed
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
    logger.info("✅ yt-dlp is available")
except ImportError:
    YT_DLP_AVAILABLE = False
    logger.warning("⚠️ yt-dlp not installed. Install it using: pip install yt-dlp")

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enable CORS for all routes

# Configuration
DOWNLOAD_FOLDER = 'downloads'
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Rate limiting storage (simple in-memory)
request_history = {}

class YouTubeDownloader:
    """Main YouTube downloader class with enhanced features"""
    
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'socket_timeout': 30,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web']
                }
            }
        }
    
    def get_video_info(self, url):
        """Get video information without downloading"""
        if not YT_DLP_AVAILABLE:
            raise Exception("yt-dlp is not installed on the server")
        
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Prepare response
                response = {
                    'success': True,
                    'title': info.get('title', 'Unknown Title'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': self.format_duration(info.get('duration', 0)),
                    'channel': info.get('channel', 'Unknown Channel'),
                    'description': info.get('description', '')[:300] + '...' if info.get('description') else 'No description',
                    'view_count': info.get('view_count', 0),
                    'upload_date': info.get('upload_date', ''),
                    'video_id': info.get('id', ''),
                    'channel_url': info.get('channel_url', ''),
                    'categories': info.get('categories', []),
                    'tags': info.get('tags', [])[:10],
                    'age_limit': info.get('age_limit', 0),
                    'is_live': info.get('is_live', False),
                    'formats': [],
                    'statistics': {
                        'views': info.get('view_count', 0),
                        'likes': info.get('like_count', 0),
                        'comments': info.get('comment_count', 0)
                    }
                }
                
                # Process available formats
                formats = []
                for f in info.get('formats', []):
                    if f.get('filesize') or f.get('url'):
                        format_info = {
                            'format_id': f.get('format_id', ''),
                            'ext': f.get('ext', ''),
                            'resolution': f.get('resolution', 'audio'),
                            'filesize': f.get('filesize', 0),
                            'format_note': f.get('format_note', ''),
                            'acodec': f.get('acodec', 'none'),
                            'vcodec': f.get('vcodec', 'none'),
                            'fps': f.get('fps', 0),
                            'tbr': f.get('tbr', 0),
                            'container': f.get('container', '')
                        }
                        
                        # Only add if it's a complete format
                        if format_info['acodec'] != 'none' or format_info['vcodec'] != 'none':
                            formats.append(format_info)
                
                # Sort and limit formats
                formats.sort(key=lambda x: (
                    0 if x['vcodec'] != 'none' else 1,  # Video first
                    -self._get_resolution_value(x['resolution']),  # Higher resolution first
                    -x.get('filesize', 0)  # Larger files first
                ))
                
                response['formats'] = formats[:20]  # Limit to 20 formats
                
                return response
                
        except Exception as e:
            logger.error(f"Error getting video info: {str(e)}")
            raise Exception(f"Failed to get video information: {str(e)}")
    
    def download_video(self, url, format_id='best'):
        """Download video in specified format"""
        if not YT_DLP_AVAILABLE:
            raise Exception("yt-dlp is not installed on the server")
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix='youtube_dl_')
        
        try:
            # Configure download options
            download_opts = {
                'format': format_id,
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [self.download_progress_hook],
                'postprocessors': [],
                'merge_output_format': 'mp4',
                'prefer_ffmpeg': True,
                'keepvideo': False,
                'noplaylist': True,
                'verbose': True
            }
            
            # Add audio conversion if requested
            if 'audio' in format_id.lower() or format_id == 'bestaudio':
                download_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
                download_opts['format'] = 'bestaudio/best'
            
            logger.info(f"Starting download: {url} with format {format_id}")
            
            with yt_dlp.YoutubeDL(download_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Handle audio conversion filename
                if download_opts['postprocessors']:
                    filename = filename.rsplit('.', 1)[0] + '.mp3'
                
                # Ensure file exists
                if not os.path.exists(filename):
                    # Try to find the actual downloaded file
                    files = [f for f in os.listdir(temp_dir) if not f.startswith('.')]
                    if files:
                        filename = os.path.join(temp_dir, files[0])
                    else:
                        raise Exception("Downloaded file not found")
                
                return filename, info.get('title', 'video')
                
        except Exception as e:
            # Cleanup on error
            self._cleanup_temp_dir(temp_dir)
            logger.error(f"Error downloading video: {str(e)}")
            raise Exception(f"Failed to download video: {str(e)}")
    
    def download_progress_hook(self, d):
        """Progress hook for downloads"""
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').strip()
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            logger.info(f"Downloading: {percent} at {speed}, ETA: {eta}")
        elif d['status'] == 'finished':
            logger.info("Download completed successfully")
        elif d['status'] == 'error':
            logger.error(f"Download error: {d.get('error', 'Unknown error')}")
    
    def _get_resolution_value(self, resolution):
        """Convert resolution string to numeric value for sorting"""
        if not resolution or resolution == 'audio':
            return 0
        
        try:
            # Extract numeric part (e.g., "1080p" -> 1080)
            import re
            match = re.search(r'(\d+)', resolution)
            return int(match.group(1)) if match else 0
        except:
            return 0
    
    def format_duration(self, seconds):
        """Format duration in seconds to HH:MM:SS"""
        if not seconds:
            return "00:00"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def _cleanup_temp_dir(self, temp_dir):
        """Clean up temporary directory"""
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory {temp_dir}: {str(e)}")

# Initialize downloader
downloader = YouTubeDownloader()

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html') if os.path.exists('templates/index.html') else app.send_static_file('index.html')

@app.route('/api/video-info', methods=['GET'])
def get_video_info():
    """Get video information without downloading"""
    # Check rate limiting
    client_ip = request.remote_addr
    current_time = datetime.now().timestamp()
    
    # Clean old requests
    for ip in list(request_history.keys()):
        if current_time - request_history[ip]['last_request'] > 60:  # 1 minute window
            del request_history[ip]
    
    # Apply rate limit (10 requests per minute per IP)
    if client_ip in request_history:
        if request_history[client_ip]['count'] >= 10:
            return jsonify({
                'error': 'Rate limit exceeded. Please wait 1 minute.',
                'retry_after': 60
            }), 429
    
    # Update request history
    if client_ip not in request_history:
        request_history[client_ip] = {'count': 1, 'last_request': current_time}
    else:
        request_history[client_ip]['count'] += 1
        request_history[client_ip]['last_request'] = current_time
    
    # Get URL parameter
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL parameter is required', 'success': False}), 400
    
    try:
        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            url = 'https://' + url
        
        logger.info(f"Fetching video info for URL: {url}")
        
        # Get video info
        video_info = downloader.get_video_info(url)
        
        # Add server info
        video_info['server_info'] = {
            'version': '2.0',
            'author': 'Subha',
            'yt_dlp_available': YT_DLP_AVAILABLE,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Successfully fetched info for: {video_info.get('title', 'Unknown')}")
        return jsonify(video_info)
        
    except Exception as e:
        logger.error(f"Error in get_video_info: {str(e)}")
        return jsonify({
            'error': str(e),
            'success': False,
            'timestamp': datetime.now().isoformat()
        }), 400

@app.route('/api/download', methods=['GET'])
def download_video():
    """Download video in specified format"""
    url = request.args.get('url')
    format_id = request.args.get('format_id', 'best')
    
    if not url:
        return jsonify({'error': 'URL parameter is required', 'success': False}), 400
    
    # Validate format_id
    allowed_formats = ['best', 'worst', 'bestvideo', 'bestaudio', 'worstvideo', 'worstaudio']
    if not any(f in format_id.lower() for f in allowed_formats + ['/', '+']):
        # Check if it's a specific format ID (e.g., "22")
        try:
            int(format_id.split('-')[0])  # Try to parse as number
        except:
            return jsonify({'error': 'Invalid format ID', 'success': False}), 400
    
    temp_dir = None
    
    try:
        logger.info(f"Download request: {url} with format {format_id}")
        
        # Download video
        filename, title = downloader.download_video(url, format_id)
        
        # Clean filename for download
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        download_name = f"{safe_title}.{filename.split('.')[-1]}"
        
        # Log download completion
        file_size = os.path.getsize(filename)
        logger.info(f"Download completed: {download_name} ({file_size} bytes)")
        
        # Send file
        response = send_file(
            filename,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/octet-stream'
        )
        
        # Cleanup after response is sent
        temp_dir = os.path.dirname(filename)
        
        @response.call_on_close
        def cleanup():
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.info(f"Cleaned up: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {temp_dir}: {str(e)}")
        
        # Add download headers
        response.headers['X-File-Name'] = download_name
        response.headers['X-File-Size'] = file_size
        response.headers['X-Content-Type'] = 'video/mp4' if filename.endswith('.mp4') else 'audio/mpeg'
        
        return response
        
    except Exception as e:
        # Cleanup on error
        if temp_dir and os.path.exists(temp_dir):
            downloader._cleanup_temp_dir(temp_dir)
        
        logger.error(f"Download error: {str(e)}")
        return jsonify({
            'error': str(e),
            'success': False,
            'timestamp': datetime.now().isoformat()
        }), 400

@app.route('/api/formats', methods=['GET'])
def get_available_formats():
    """Get all available formats for a video"""
    url = request.args.get('url')
    
    if not url:
        return jsonify({'error': 'URL parameter is required', 'success': False}), 400
    
    if not YT_DLP_AVAILABLE:
        return jsonify({
            'error': 'Server error: yt-dlp not installed',
            'success': False
        }), 500
    
    try:
        ydl_opts = {
            'listformats': True,
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            for f in info.get('formats', []):
                format_info = {
                    'format_id': f.get('format_id'),
                    'ext': f.get('ext'),
                    'resolution': f.get('resolution', 'N/A'),
                    'filesize': f.get('filesize', 0),
                    'format_note': f.get('format_note', ''),
                    'quality': f.get('quality', 0),
                    'vcodec': f.get('vcodec', 'none'),
                    'acodec': f.get('acodec', 'none'),
                }
                formats.append(format_info)
            
            return jsonify({
                'success': True,
                'formats': formats,
                'total': len(formats),
                'video_id': info.get('id', '')
            })
            
    except Exception as e:
        logger.error(f"Error getting formats: {str(e)}")
        return jsonify({
            'error': str(e),
            'success': False
        }), 400

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'server': 'YouTube Downloader API',
        'version': '2.0',
        'author': 'Subha',
        'timestamp': datetime.now().isoformat(),
        'yt_dlp_available': YT_DLP_AVAILABLE,
        'python_version': os.sys.version,
        'download_folder': DOWNLOAD_FOLDER,
        'temp_dir': tempfile.gettempdir(),
        'features': [
            'video_info',
            'download',
            'format_listing',
            'rate_limiting',
            'progress_tracking'
        ]
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get server statistics"""
    return jsonify({
        'success': True,
        'stats': {
            'active_downloads': 0,  # Could implement tracking
            'total_space': shutil.disk_usage('.').total,
            'free_space': shutil.disk_usage('.').free,
            'uptime': 'N/A',  # Could implement uptime tracking
            'requests_served': len(request_history),
            'version': '2.0'
        }
    })

@app.route('/api/search', methods=['GET'])
def search_videos():
    """Search YouTube videos (placeholder for future feature)"""
    query = request.args.get('q')
    
    if not query:
        return jsonify({'error': 'Query parameter is required', 'success': False}), 400
    
    return jsonify({
        'success': True,
        'message': 'Search feature coming soon',
        'query': query,
        'results': []
    })

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Endpoint not found',
        'success': False,
        'available_endpoints': [
            '/api/video-info',
            '/api/download',
            '/api/formats',
            '/api/health',
            '/api/stats'
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'error': 'Internal server error',
        'success': False,
        'timestamp': datetime.now().isoformat()
    }), 500

@app.before_request
def before_request():
    """Log all requests"""
    logger.info(f"{request.remote_addr} - {request.method} {request.path}")

if __name__ == '__main__':
    print("=" * 60)
    print("🎬 YouTube Downloader Server v2.0")
    print("👤 Created by Subha")
    print("=" * 60)
    print(f"✅ YT-DLP Available: {YT_DLP_AVAILABLE}")
    print(f"📁 Download folder: {DOWNLOAD_FOLDER}")
    print(f"🌐 Temp directory: {tempfile.gettempdir()}")
    print("=" * 60)
    print("\n🚀 Starting server...")
    print(f"🔗 Access the application at: http://localhost:5000")
    print(f"📚 API Documentation:")
    print(f"   GET  /api/video-info?url=URL     - Get video information")
    print(f"   GET  /api/download?url=URL       - Download video")
    print(f"   GET  /api/health                 - Health check")
    print(f"   GET  /api/stats                  - Server statistics")
    print("=" * 60)
    print("\n💡 To install missing dependencies:")
    print("   pip install flask flask-cors yt-dlp")
    print("=" * 60)
    
    # Create necessary directories
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # Run the app with production settings
    app.run(
        debug=False,  # Set to False for production
        host='0.0.0.0',
        port=5000,
        threaded=True
    )