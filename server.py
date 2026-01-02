import os
import sys
import logging
import tempfile
import shutil
import time
import random
import json
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
        # Enhanced headers and options to bypass bot detection
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1'
        ]
        
        # Try to load cookies from environment variable or file
        self.cookie_opts = {}
        cookie_path = os.environ.get('COOKIES_FILE', 'cookies.txt')
        
        if os.path.exists(cookie_path):
            self.cookie_opts = {'cookiefile': cookie_path}
            logger.info(f"Using cookies from: {cookie_path}")
        else:
            logger.warning("No cookies file found. Some videos may be blocked.")

    def get_info(self, url):
        if not YT_DLP_AVAILABLE:
            raise Exception("Server Error: yt-dlp is missing.")
        
        # Try 3 different strategies
        strategies = [
            self._try_extract_with_ios,
            self._try_extract_with_android,
            self._try_extract_with_web
        ]
        
        last_error = None
        
        for strategy in strategies:
            try:
                logger.info(f"Trying strategy: {strategy.__name__}")
                return strategy(url)
            except Exception as e:
                last_error = e
                logger.warning(f"Strategy failed: {str(e)}")
                time.sleep(1)  # Brief pause between attempts
        
        # If all strategies failed
        error_msg = str(last_error)
        if "Sign in" in error_msg or "bot" in error_msg:
            raise Exception(
                "YouTube requires authentication. To fix this:\n"
                "1. Log into YouTube in your browser\n"
                "2. Export cookies using 'Get cookies.txt' extension\n"
                "3. Save as 'cookies.txt' in the server directory\n"
                "4. Restart the server"
            )
        else:
            raise Exception(f"Failed to fetch video: {error_msg}")

    def _try_extract_with_ios(self, url):
        """iOS client strategy - usually works for most videos"""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios'],
                    'player_skip': ['webpage']
                }
            },
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
            'referer': 'https://www.youtube.com/',
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
            },
            **self.cookie_opts
        }
        
        return self._extract_with_options(url, opts)

    def _try_extract_with_android(self, url):
        """Android client strategy"""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'geo_bypass': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'player_skip': ['webpage', 'js']
                }
            },
            'user_agent': 'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
            'referer': 'https://www.youtube.com/',
            **self.cookie_opts
        }
        
        return self._extract_with_options(url, opts)

    def _try_extract_with_web(self, url):
        """Web client with random user agent"""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'geo_bypass': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web'],
                    'player_skip': []
                }
            },
            'user_agent': random.choice(self.user_agents),
            'referer': 'https://www.youtube.com/',
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            },
            **self.cookie_opts
        }
        
        return self._extract_with_options(url, opts)

    def _extract_with_options(self, url, ydl_opts):
        """Common extraction logic"""
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

            return {
                'success': True,
                'title': info.get('title', 'Unknown Title'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': self._format_duration(info.get('duration')),
                'channel': info.get('uploader', 'Unknown Channel'),
                'view_count': info.get('view_count', 0),
                'video_id': info.get('id', ''),
                'original_url': url,
                'formats': processed_formats[:20]  # Limit to 20 formats
            }

    def download_stream(self, url, format_id):
        temp_dir = tempfile.mkdtemp()
        
        # Download options
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': format_id,
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'user_agent': random.choice(self.user_agents),
            'referer': 'https://www.youtube.com/',
            'geo_bypass': True,
            **self.cookie_opts
        }

        # Audio conversion
        if 'audio' in str(format_id).lower() or format_id.endswith('m4a'):
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # If converted to mp3
                if 'postprocessors' in ydl_opts:
                    base, _ = os.path.splitext(filename)
                    filename = base + ".mp3"
                    
                return filename, temp_dir
        except Exception as e:
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
        "cookies_available": bool(handler.cookie_opts),
        "strategies": ["ios", "android", "web"],
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
        file_path, temp_dir = handler.download_stream(url, format_id)
        filename = os.path.basename(file_path)
        
        # Clean filename
        filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).strip()
        
        # Read file
        with open(file_path, 'rb') as f:
            data = f.read()
            
        # Cleanup temp files
        try:
            shutil.rmtree(temp_dir)
        except OSError:
            pass
        
        return Response(
            data, 
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/octet-stream"
            }
        )
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "yt_dlp": YT_DLP_AVAILABLE
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)