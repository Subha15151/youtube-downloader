import os
import sys
import logging
import tempfile
import shutil
import time
import random
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("YTDownloader")

# Check for yt-dlp
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    logger.error("yt-dlp not found! Install it via requirements.txt")

app = Flask(__name__)
CORS(app)

class YouTubeHandler:
    def __init__(self):
        # Check for cookies file
        self.cookie_paths = [
            'cookies.txt',
            'www.youtube.com_cookies.txt',
            './config/cookies.txt'
        ]
        
        self.cookies_file = None
        self.cookie_opts = {}
        
        for path in self.cookie_paths:
            if os.path.exists(path):
                self.cookies_file = path
                self.cookie_opts = {'cookiefile': path}
                logger.info(f"✅ Cookies file found: {path}")
                break
        
        if not self.cookies_file:
            logger.warning("⚠️ No cookies file found. Some videos may be blocked.")
        else:
            # Verify cookies file is valid
            try:
                with open(self.cookies_file, 'r') as f:
                    content = f.read()
                    if '# Netscape HTTP Cookie File' in content:
                        logger.info("✅ Valid Netscape format cookies detected")
                    if 'youtube.com' in content:
                        logger.info("✅ YouTube cookies found in file")
            except:
                pass
        
        # Enhanced options with cookies
        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'web'],
                    'player_skip': ['webpage']
                }
            },
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            **self.cookie_opts  # Add cookies if available
        }

    def get_info(self, url):
        if not YT_DLP_AVAILABLE:
            raise Exception("Server Error: yt-dlp is missing.")
        
        # Try with cookies first, then without if fails
        strategies = [
            self._try_with_cookies,
            self._try_without_cookies
        ]
        
        last_error = None
        
        for strategy in strategies:
            try:
                logger.info(f"Trying strategy: {strategy.__name__}")
                return strategy(url)
            except Exception as e:
                last_error = e
                logger.warning(f"Strategy failed: {str(e)}")
                time.sleep(1)
        
        # If all strategies failed
        error_msg = str(last_error)
        raise Exception(f"Failed to fetch video: {error_msg}")

    def _try_with_cookies(self, url):
        """Try extraction with cookies"""
        if not self.cookies_file:
            raise Exception("No cookies file available")
        
        opts = self.base_opts.copy()
        opts['cookiefile'] = self.cookies_file
        
        logger.info("Using cookies for authentication...")
        return self._extract_with_options(url, opts, "with_cookies")

    def _try_without_cookies(self, url):
        """Try extraction without cookies (fallback)"""
        opts = self.base_opts.copy()
        # Remove cookies
        if 'cookiefile' in opts:
            del opts['cookiefile']
        
        # Try different user agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36'
        ]
        opts['user_agent'] = random.choice(user_agents)
        
        logger.info("Trying without cookies...")
        return self._extract_with_options(url, opts, "without_cookies")

    def _extract_with_options(self, url, ydl_opts, strategy_name=""):
        """Common extraction logic"""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Filter Formats
                processed_formats = []
                formats = info.get('formats', [])
                
                for f in formats:
                    # Skip streaming formats
                    if f.get('protocol') in ['m3u8', 'm3u8_native']:
                        continue
                        
                    is_video = f.get('vcodec') != 'none'
                    is_audio = f.get('acodec') != 'none'
                    
                    if not is_video and not is_audio:
                        continue
                    
                    # Get filesize
                    size = f.get('filesize') or f.get('filesize_approx') or 0

                    processed_formats.append({
                        'format_id': f['format_id'],
                        'ext': f['ext'],
                        'filesize': size,
                        'resolution': f.get('resolution', 'audio only'),
                        'quality': f.get('height', 0),
                        'vcodec': f.get('vcodec', 'none'),
                        'acodec': f.get('acodec', 'none'),
                        'note': f.get('format_note', '')
                    })
                
                # Sort by quality
                processed_formats.sort(key=lambda x: x.get('quality', 0), reverse=True)
                
                # Log success
                logger.info(f"✅ Successfully fetched video using {strategy_name}")
                logger.info(f"   Title: {info.get('title', 'Unknown')[:50]}...")
                logger.info(f"   Formats found: {len(processed_formats)}")

                return {
                    'success': True,
                    'title': info.get('title', 'Unknown Title'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': self._format_duration(info.get('duration')),
                    'channel': info.get('uploader', 'Unknown Channel'),
                    'view_count': info.get('view_count', 0),
                    'video_id': info.get('id', ''),
                    'original_url': url,
                    'cookies_used': 'cookiefile' in ydl_opts,
                    'formats': processed_formats[:20]
                }
                
        except Exception as e:
            logger.error(f"Extraction failed with {strategy_name}: {str(e)}")
            raise

    def download_stream(self, url, format_id):
        temp_dir = tempfile.mkdtemp()
        
        # Download options
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': format_id,
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'geo_bypass': True,
            **self.cookie_opts  # Include cookies for download too
        }

        # Audio conversion
        if 'audio' in str(format_id).lower() or format_id.endswith('m4a'):
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }]

        try:
            logger.info(f"Starting download: {url[:50]}... with format {format_id}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # If converted to mp3
                if 'postprocessors' in ydl_opts:
                    base, _ = os.path.splitext(filename)
                    filename = base + ".mp3"
                
                logger.info(f"✅ Download completed: {filename}")
                return filename, temp_dir
                
        except Exception as e:
            logger.error(f"❌ Download failed: {str(e)}")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise e

    @staticmethod
    def _format_duration(seconds):
        if not seconds:
            return "00:00"
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

handler = YouTubeHandler()

# --- ROUTES ---

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "version": "2.0",
        "cookies_available": bool(handler.cookies_file),
        "cookies_file": handler.cookies_file,
        "timestamp": time.time()
    })

@app.route('/api/video-info', methods=['GET'])
def video_info():
    url = request.args.get('url')
    if not url:
        return jsonify({"success": False, "error": "URL is required"}), 400
    
    # Validate YouTube URL
    if 'youtube.com' not in url and 'youtu.be' not in url:
        return jsonify({"success": False, "error": "Invalid YouTube URL"}), 400
    
    try:
        logger.info(f"Fetching video info for: {url[:80]}...")
        data = handler.get_info(url)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error fetching video info: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download():
    url = request.args.get('url')
    format_id = request.args.get('format_id', 'best')
    
    if not url:
        return jsonify({"error": "URL required"}), 400

    try:
        logger.info(f"Download request: {url[:50]}... format: {format_id}")
        file_path, temp_dir = handler.download_stream(url, format_id)
        filename = os.path.basename(file_path)
        
        # Clean filename for safe download
        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).strip()
        
        # Read file
        with open(file_path, 'rb') as f:
            data = f.read()
        
        file_size = len(data)
        logger.info(f"✅ File ready: {safe_filename} ({file_size} bytes)")
            
        # Cleanup temp files
        try:
            shutil.rmtree(temp_dir)
        except OSError:
            pass
        
        return Response(
            data, 
            headers={
                "Content-Disposition": f"attachment; filename=\"{safe_filename}\"",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(file_size)
            }
        )
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "cookies": bool(handler.cookies_file),
        "yt_dlp": YT_DLP_AVAILABLE,
        "timestamp": time.time()
    })

@app.route('/api/debug/cookies', methods=['GET'])
def debug_cookies():
    """Debug endpoint to check cookies"""
    if not handler.cookies_file:
        return jsonify({"cookies": "not_found"})
    
    try:
        with open(handler.cookies_file, 'r') as f:
            lines = f.readlines()
            youtube_lines = [l for l in lines if 'youtube.com' in l]
            
            return jsonify({
                "cookies": "found",
                "file": handler.cookies_file,
                "total_lines": len(lines),
                "youtube_cookies": len(youtube_lines),
                "sample": lines[:3] if lines else []
            })
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Starting YTDownloader server on port {port}")
    logger.info(f"📁 Cookies file: {handler.cookies_file or 'Not found'}")
    app.run(host='0.0.0.0', port=port, debug=False)