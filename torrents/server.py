from flask import Flask, request, send_from_directory, abort
import os

app = Flask(__name__)
TORRENT_DIR = 'torrents'  # Directory to store torrent files


@app.route('/upload', methods=['POST'])
def upload_torrent():
    file = request.files['file']
    if file and file.filename.endswith('.torrent'):
        file.save(os.path.join(TORRENT_DIR, file.filename))
        return "File uploaded successfully", 200
    return "Invalid file", 400


@app.route('/download/<filename>', methods=['GET'])
def download_torrent(filename):
    if filename.endswith('.torrent'):
        return send_from_directory(TORRENT_DIR, filename)
    return abort(404)


if __name__ == '__main__':
    os.makedirs(TORRENT_DIR, exist_ok=True)
    app.run(host='0.0.0.0', port=5000)
