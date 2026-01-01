import os
import sys
import logging
import tempfile
import shutil
from datetime import datetime
from urllib.parse import urlparse

# Third-party imports
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS

# Check if yt-dlp is installed
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    print("⚠️  WARNING: yt-dlp not found. Install it with: pip install yt-dlp")

# ==========================================
# 1. CONFIGURATION & LOGGING
# ==========================================
app = Flask(__name__)
CORS(app)  # Allow all domains (needed for GitHub Pages + Render)

# Setup professional logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("YTDownloader")

# Constants
DOWNLOAD_DIR = tempfile.gettempdir()  # Use system temp folder

# ==========================================
# 2. CORE DOWNLOADER CLASS
# ==========================================
class YouTubeHandler:
    def __init__(self):
        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            # User-Agent to avoid bot detection
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }

    def get_info(self, url):
        """Extracts video metadata without downloading"""
        if not YT_DLP_AVAILABLE:
            raise Exception("Server Error: yt-dlp is missing.")

        try:
            with yt_dlp.YoutubeDL(self.base_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Filter and process formats for the UI
                processed_formats = []
                for f in info.get('formats', []):
                    # Skip incomplete formats (video only without audio is fine, but we label it)
                    if f.get('protocol') == 'm3u8_native': continue 

                    # Determine type
                    is_video = f.get('vcodec') != 'none'
                    is_audio = f.get('acodec') != 'none'
                    
                    if not is_video and not is_audio: continue

                    processed_formats.append({
                        'format_id': f['format_id'],
                        'ext': f['ext'],
                        'filesize': f.get('filesize') or f.get('filesize_approx') or 0,
                        'resolution': f.get('resolution', 'audio only'),
                        'quality': f.get('height', 0),
                        'vcodec': f.get('vcodec'),
                        'acodec': f.get('acodec'),
                        'note': f.get('format_note', '')
                    })

                # Sort: Highest resolution first
                processed_formats.sort(key=lambda x: x.get('quality', 0), reverse=True)

                return {
                    'success': True,
                    'title': info.get('title'),
                    'thumbnail': info.get('thumbnail'),
                    'duration': self._format_duration(info.get('duration')),
                    'channel': info.get('uploader'),
                    'view_count': info.get('view_count'),
                    'video_id': info.get('id'),
                    'original_url': url,
                    'formats': processed_formats[:20]  # Limit to top 20 to save bandwidth
                }
        except Exception as e:
            logger.error(f"Extraction Error: {str(e)}")
            raise Exception(f"Could not fetch video: {str(e)}")

    def download_stream(self, url, format_id):
        """Downloads the video to a temp file and returns the path"""
        temp_dir = tempfile.mkdtemp()
        
        # Configure specific download options
        ydl_opts = self.base_opts.copy()
        ydl_opts.update({
            'format': format_id,
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
        })

        # Special handling for Audio-only (convert to MP3 if needed)
        if 'audio' in str(format_id):
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Adjust filename if post-processing changed extension (e.g. mp4 -> mp3)
                if 'audio' in str(format_id):
                    base, _ = os.path.splitext(filename)
                    filename = base + ".mp3"

                return filename, temp_dir
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise e

    @staticmethod
    def _format_duration(seconds):
        if not seconds: return "00:00"
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

# Initialize Handler
handler = YouTubeHandler()

# ==========================================
# 3. API ROUTES
# ==========================================

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "YTDownloader Pro API",
        "version": "2.0",
        "message": "Use the /api endpoints to interact."
    })

@app.route('/api/video-info', methods=['GET'])
def video_info():
    url = request.args.get('url')
    if not url:
        return jsonify({"success": False, "error": "URL is required"}), 400

    try:
        data = handler.get_info(url)
        return jsonify(data)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download():
    url = request.args.get('url')
    format_id = request.args.get('format_id', 'best')

    if not url:
        return jsonify({"error": "URL required"}), 400

    try:
        # 1. Download to temp folder
        file_path, temp_dir = handler.download_stream(url, format_id)
        filename = os.path.basename(file_path)

        # 2. Cleanup Function (Runs after download finishes)
        def cleanup_temp():
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temp dir: {temp_dir}")
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

        # 3. Send file to user
        # Using a generator to ensure file is read before cleanup
        with open(file_path, 'rb') as f:
            data = f.read()

        # Clean up immediately after reading into memory (for small files)
        # For large files, you'd want to stream, but memory is safer for Render Free Tier
        cleanup_temp()

        return Response(
            data,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/octet-stream",
            }
        )

    except Exception as e:
        logger.error(f"Download Route Error: {e}")
        return jsonify({"error": "Download failed. Please try a different quality."}), 500

# ==========================================
# 4. SERVER ENTRY POINT
# ==========================================
if __name__ == '__main__':
    # ⚠️ CRITICAL FOR RENDER DEPLOYMENT
    # Render assigns a random port in the environment variable 'PORT'
    port = int(os.environ.get("PORT", 5000))
    
    logger.info(f"🚀 Server starting on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)