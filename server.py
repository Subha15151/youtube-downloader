import os
import sys
import logging
import tempfile
import shutil
import time
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
        # iOS Mode (Strongest Bypass)
        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'geo_bypass': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios']
                }
            }
        }

    def get_info(self, url):
        if not YT_DLP_AVAILABLE:
            raise Exception("Server Error: yt-dlp is missing.")
        
        try:
            with yt_dlp.YoutubeDL(self.base_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Filter Formats
                processed_formats = []
                formats = info.get('formats', [])
                
                for f in formats:
                    # Skip m3u8 (streaming) formats
                    if f.get('protocol') == 'm3u8_native':
                        continue
                        
                    is_video = f.get('vcodec') != 'none'
                    is_audio = f.get('acodec') != 'none'
                    
                    if not is_video and not is_audio:
                        continue
                    
                    # Safe filesize extraction
                    size = f.get('filesize')
                    if not size:
                        size = f.get('filesize_approx') or 0

                    processed_formats.append({
                        'format_id': f['format_id'],
                        'ext': f['ext'],
                        'filesize': size,
                        'resolution': f.get('resolution', 'audio only'),
                        'quality': f.get('height', 0),
                        'note': f.get('format_note', '')
                    })
                
                # Sort: Best quality first
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
                    'formats': processed_formats[:15]
                }
        except Exception as e:
            logger.error(f"Extraction Error: {str(e)}")
            raise Exception(f"YouTube Blocked Request: {str(e)}")

    def download_stream(self, url, format_id):
        temp_dir = tempfile.mkdtemp()
        
        # Options specific to this download
        ydl_opts = self.base_opts.copy()
        ydl_opts['format'] = format_id
        ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')

        # Audio conversion logic
        if 'audio' in str(format_id):
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # If converted to mp3, the extension changes
                if 'audio' in str(format_id):
                    base, _ = os.path.splitext(filename)
                    filename = base + ".mp3"
                    
                return filename, temp_dir
        except Exception as e:
            # Cleanup on failure
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
        "mode": "iOS Bypass Active",
        "time": time.time()
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
        file_path, temp_dir = handler.download_stream(url, format_id)
        filename = os.path.basename(file_path)
        
        # Read file into memory
        with open(file_path, 'rb') as f:
            data = f.read()
            
        # Cleanup temp files immediately
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
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Get port securely
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)