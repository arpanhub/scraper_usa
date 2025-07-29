from flask import Flask, render_template, request, send_file, jsonify, session
import os
import uuid
import threading
from werkzeug.utils import secure_filename
import time
from your_scraper import LinkedInJobScraper  # Your original scraper

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULTS_FOLDER'] = 'results'

# Create folders
os.makedirs('uploads', exist_ok=True)
os.makedirs('results', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Store job status
jobs = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and file.filename.endswith('.xlsx'):
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        session['job_id'] = job_id
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
        file.save(filepath)
        
        # Initialize job status
        jobs[job_id] = {
            'status': 'queued',
            'progress': 0,
            'total': 0,
            'current_company': '',
            'start_time': time.time(),
            'input_file': filepath,
            'output_file': None
        }
        
        # Start scraping in background
        thread = threading.Thread(target=run_scraper, args=(job_id, filepath))
        thread.daemon = True
        thread.start()
        
        return jsonify({'job_id': job_id, 'message': 'File uploaded successfully'})
    
    return jsonify({'error': 'Invalid file format'}), 400

@app.route('/status/<job_id>')
def job_status(job_id):
    if job_id in jobs:
        job = jobs[job_id]
        elapsed = time.time() - job['start_time']
        return jsonify({
            'status': job['status'],
            'progress': job['progress'],
            'total': job['total'],
            'current_company': job['current_company'],
            'elapsed_time': f"{elapsed/60:.1f} minutes",
            'download_ready': job['output_file'] is not None
        })
    return jsonify({'error': 'Job not found'}), 404

@app.route('/download/<job_id>')
def download_result(job_id):
    if job_id in jobs and jobs[job_id]['output_file']:
        return send_file(jobs[job_id]['output_file'], as_attachment=True)
    return jsonify({'error': 'File not ready'}), 404

def run_scraper(job_id, input_file):
    """Run scraper in background with progress updates"""
    try:
        jobs[job_id]['status'] = 'running'
        
        # Initialize scraper with progress callback
        scraper = LinkedInJobScraperWithProgress(
            email="arpan@propel.bz",
            password="B,Zhs-ccjB^d5_e.",
            input_excel_file=input_file,
            progress_callback=lambda current, total, company: update_progress(job_id, current, total, company)
        )
        
        # Run scraper
        output_file = os.path.join(app.config['RESULTS_FOLDER'], f"results_{job_id}.xlsx")
        scraper.run_scraper_with_output(output_file)
        
        jobs[job_id]['output_file'] = output_file
        jobs[job_id]['status'] = 'completed'
        
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error'] = str(e)

def update_progress(job_id, current, total, company):
    """Update job progress"""
    if job_id in jobs:
        jobs[job_id]['progress'] = current
        jobs[job_id]['total'] = total
        jobs[job_id]['current_company'] = company

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))