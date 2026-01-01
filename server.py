import os
import sys
import logging
import tempfile
import shutil
import random
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS

# Check for yt-dlp
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    print("⚠️  WARNING: yt-dlp not found. Install it with: pip install yt-dlp")

app = Flask(__name__)
CORS(app)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("YTDownloader")

class YouTubeHandler:
    def __init__(self):
        # 🟢 MAXIMUM STRENGTH ANTI-BOT SETTINGS (iOS MODE)
        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'geo_bypass': False, # Disable this to look less suspicious
            
            # Pretend to be an iPhone (Strongest Bypass currently)
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'web_creator']
                }
            },
            
            # Real iPhone User-Agent
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
        }

    def get_info(self, url):
        if not YT_DLP_AVAILABLE: raise Exception("Server Error: yt-dlp is missing.")
        
        try:
            with yt_dlp.YoutubeDL(self.base_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Filter Formats
                processed_formats = []
                for f in info.get('formats', []):
                    if f.get('protocol') == 'm3u8_native': continue
                    is_video = f.get('vcodec') != 'none'
                    is_audio = f.get('acodec') != 'none'
                    if not is_video and not is_audio: continue
                    
                    processed_formats.append({
                        'format_id': f['format_id'],
                        'ext': f['ext'],
                        'filesize': f.get('filesize') or f.get('filesize_approx') or 0,
                        'resolution': f.get('resolution', 'audio only'),
                        'quality': f.get('height', 0),
                        'note': f.get('format_note', '')
                    })
                
                # Sort best quality first
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
        ydl_opts = self.base_opts.copy()
        ydl_opts.update({
            'format': format_id,
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        })

        if 'audio' in str(format_id):
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
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
        if h > 0: return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

handler = YouTubeHandler()

@app.route('/')
def home():
    # This message helps you verify if the new code is running
    return jsonify({"status": "online", "mode": "iOS Bypass Active"})

@app.route('/api/video-info', methods=['GET'])
def video_info():
    url = request.args.get('url')
    if not url: return jsonify({"success": False, "error": "URL is required"}), 400
    try:
        data = handler.get_info(url)
        return jsonify(data)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download():
    url = request.args.get('url')
    format_id = request.args.get('format_id', 'best')
    try:
        file_path, temp_dir = handler.download_stream(url, format_id)
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            data = f.read()
            
        try: shutil.rmtree(temp_dir)
        except: pass
        
        return Response(data, headers={"Content-Disposition": f"attachment; filename={filename}", "Content-Type": "application/octet-stream"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port))
