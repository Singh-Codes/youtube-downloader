from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import yt_dlp
import os
import json
from datetime import datetime
import threading
from cryptography.fernet import Fernet
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///youtube_downloader.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['DOWNLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')

# Global progress tracking
download_progress = defaultdict(dict)
progress_lock = threading.Lock()

if not os.path.exists(app.config['DOWNLOAD_FOLDER']):
    os.makedirs(app.config['DOWNLOAD_FOLDER'])

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Generate encryption key for sensitive data
encryption_key = os.getenv('ENCRYPTION_KEY')
if not encryption_key:
    if os.path.exists('encryption_key.key'):
        with open('encryption_key.key', 'rb') as key_file:
            encryption_key = key_file.read()
    else:
        encryption_key = Fernet.generate_key()
        with open('encryption_key.key', 'wb') as key_file:
            key_file.write(encryption_key)

fernet = Fernet(encryption_key if isinstance(encryption_key, bytes) else encryption_key.encode())

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    downloads = db.relationship('Download', backref='user', lazy=True)

class Download(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_url = db.Column(db.String(500), nullable=False)
    video_title = db.Column(db.String(500))
    format_id = db.Column(db.String(20))
    download_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')
    file_path = db.Column(db.String(500))
    error = db.Column(db.String(500))

# Create database tables
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def get_progress_hook(download_id):
    def progress_hook(d):
        with progress_lock:
            if d['status'] == 'downloading':
                download_progress[download_id] = {
                    'status': 'downloading',
                    'downloaded_bytes': d.get('downloaded_bytes', 0),
                    'total_bytes': d.get('total_bytes', 0),
                    'speed': d.get('speed', 0),
                    'eta': d.get('eta', 0),
                    'filename': d.get('filename', '')
                }
            elif d['status'] == 'finished':
                download_progress[download_id] = {
                    'status': 'finished',
                    'filename': d.get('filename', '')
                }
            elif d['status'] == 'error':
                download_progress[download_id] = {
                    'status': 'error',
                    'error': str(d.get('error', 'Unknown error'))
                }
    return progress_hook

def download_video_task(url, format_id, download_id, user_id):
    download_path = os.path.join(app.config['DOWNLOAD_FOLDER'], str(user_id))
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    ydl_opts = {
        'format': format_id,
        'progress_hooks': [get_progress_hook(download_id)],
        'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
        'quiet': False,
        'no_warnings': False,
        'ignoreerrors': True,
        'no_check_certificate': True,
        'socket_timeout': 30,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate'
        },
        'extractor_args': {
            'youtube': {
                'formats': 'web'  # Only use web formats, skip ios formats
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url)
                with app.app_context():
                    download = Download.query.get(download_id)
                    if download:
                        download.video_title = info.get('title', 'Unknown')
                        download.status = 'completed'
                        download.file_path = os.path.join(download_path, f"{info['title']}.{info['ext']}")
                        db.session.commit()
            except Exception as e:
                app.logger.error(f'Download error: {str(e)}')
                with app.app_context():
                    download = Download.query.get(download_id)
                    if download:
                        download.status = 'failed'
                        download.error = str(e)
                        db.session.commit()
    except Exception as e:
        app.logger.error(f'YoutubeDL error: {str(e)}')
        with app.app_context():
            download = Download.query.get(download_id)
            if download:
                download.status = 'failed'
                download.error = str(e)
                db.session.commit()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    downloads = Download.query.filter_by(user_id=current_user.id).order_by(Download.download_date.desc()).all()
    return render_template('dashboard.html', downloads=downloads)

@app.route('/get_formats', methods=['POST'])
@login_required
def get_formats():
    try:
        data = request.get_json()
        url = data.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'})

        app.logger.info(f'Getting formats for URL: {url}')
        
        ydl_opts = {
            'format': 'best',  # Default to best format since ffmpeg might not be available
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'force_generic_extractor': False,
            'ignoreerrors': True,
            'no_check_certificate': True,
            'socket_timeout': 30,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return jsonify({'error': 'Could not fetch video information'})

                title = info.get('title', 'Unknown Title')
                app.logger.info(f'Video title: {title}')
                
                # Filter and process formats
                formats = []
                available_formats = info.get('formats', [])
                
                if not available_formats:
                    # If no formats found, try to get at least the best format
                    best_format = info.get('format', {})
                    if isinstance(best_format, dict):
                        available_formats = [best_format]
                    else:
                        available_formats = []

                for f in available_formats:
                    try:
                        if not isinstance(f, dict):
                            continue

                        # Get format details with safe fallbacks
                        format_id = str(f.get('format_id', ''))
                        ext = str(f.get('ext', 'mp4')).lower()
                        
                        # Skip non-video formats
                        if ext not in ['mp4', 'webm', 'mkv']:
                            continue
                            
                        # Get resolution
                        height = 0
                        try:
                            height = int(f.get('height', 0))
                        except (TypeError, ValueError):
                            # Try to extract height from format note
                            format_note = str(f.get('format_note', ''))
                            if 'p' in format_note:
                                try:
                                    height = int(format_note.split('p')[0])
                                except (ValueError, IndexError):
                                    continue
                            else:
                                continue

                        if height <= 0:
                            continue

                        # Determine quality label
                        if height >= 1080:
                            quality = '1080p'
                        elif height >= 720:
                            quality = '720p'
                        elif height >= 480:
                            quality = '480p'
                        elif height >= 360:
                            quality = '360p'
                        else:
                            quality = f'{height}p'

                        # Get filesize with safe fallback
                        filesize = 0
                        try:
                            filesize = int(f.get('filesize', 0))
                            if filesize == 0:
                                filesize = int(f.get('filesize_approx', 0))
                        except (TypeError, ValueError):
                            pass

                        # Format filesize display
                        if filesize > 1024*1024*1024:
                            filesize_display = f'{filesize/(1024*1024*1024):.1f} GB'
                        elif filesize > 1024*1024:
                            filesize_display = f'{filesize/(1024*1024):.1f} MB'
                        elif filesize > 1024:
                            filesize_display = f'{filesize/1024:.1f} KB'
                        elif filesize > 0:
                            filesize_display = f'{filesize} B'
                        else:
                            filesize_display = 'Unknown size'

                        # Get video codec and FPS
                        vcodec = str(f.get('vcodec', 'unknown'))
                        fps = 'N/A'
                        try:
                            fps_val = int(f.get('fps', 0))
                            if fps_val > 0:
                                fps = str(fps_val)
                        except (TypeError, ValueError):
                            pass

                        formats.append({
                            'format_id': format_id,
                            'ext': ext,
                            'quality': quality,
                            'filesize': filesize,
                            'filesize_display': filesize_display,
                            'vcodec': vcodec,
                            'fps': fps
                        })

                    except Exception as e:
                        app.logger.error(f'Error processing format: {str(e)}')
                        continue

                # Sort formats by quality (height) in descending order
                def get_quality_value(format_dict):
                    try:
                        quality = format_dict.get('quality', '0p')
                        return int(quality.replace('p', ''))
                    except (ValueError, AttributeError):
                        return 0

                formats.sort(key=get_quality_value, reverse=True)
                
                if not formats:
                    return jsonify({'error': 'No suitable formats found'})

                return jsonify({
                    'title': title,
                    'formats': formats
                })

            except Exception as e:
                app.logger.error(f'Error extracting info: {str(e)}')
                return jsonify({'error': str(e)})

    except Exception as e:
        app.logger.error(f'Error getting formats: {str(e)}')
        return jsonify({'error': str(e)})

@app.route('/download', methods=['POST'])
@login_required
def download():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        url = data.get('url')
        format_id = data.get('format_id')
        
        if not url or not format_id:
            return jsonify({'error': 'URL and format_id are required'}), 400

        app.logger.info(f'Starting download for URL: {url}, format: {format_id}')

        # Get video info first
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return jsonify({'error': 'Could not fetch video information'}), 400
                
                video_title = info.get('title', 'Unknown Title')
                
                # Create download record
                download = Download(
                    user_id=current_user.id,
                    video_url=url,
                    video_title=video_title,
                    format_id=format_id,
                    download_date=datetime.now(),
                    status='pending'
                )
                
                db.session.add(download)
                db.session.commit()
                
                # Start download task
                thread = threading.Thread(
                    target=download_video_task,
                    args=(url, format_id, download.id, current_user.id)
                )
                thread.start()
                
                return jsonify({
                    'message': 'Download started',
                    'download_id': download.id
                })

        except Exception as e:
            app.logger.error(f'Error getting video info: {str(e)}')
            return jsonify({'error': f'Error getting video info: {str(e)}'}), 400

    except Exception as e:
        app.logger.error(f'Error starting download: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/progress/<int:download_id>')
@login_required
def get_progress(download_id):
    with progress_lock:
        progress = download_progress.get(download_id, {})
        if not progress:
            download = Download.query.get(download_id)
            if download:
                return jsonify({
                    'status': download.status,
                    'error': download.error if download.status == 'failed' else None
                })
        return jsonify(progress)

@app.route('/download_file/<int:download_id>')
@login_required
def download_file(download_id):
    download = Download.query.get_or_404(download_id)
    
    # Check if the download belongs to the current user
    if download.user_id != current_user.id:
        abort(403)
    
    if not download.file_path or not os.path.exists(download.file_path):
        flash('File not found', 'error')
        return redirect(url_for('dashboard'))
    
    # Get the directory and filename
    directory = os.path.dirname(download.file_path)
    filename = os.path.basename(download.file_path)
    
    return send_from_directory(
        directory,
        filename,
        as_attachment=True,
        download_name=filename
    )

@app.errorhandler(401)
def unauthorized(e):
    if request.is_json:
        return jsonify({'error': 'Authentication required'}), 401
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_error(e):
    if request.is_json:
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('error.html', error=str(e)), 500

if __name__ == '__main__':
    app.run(debug=True)
