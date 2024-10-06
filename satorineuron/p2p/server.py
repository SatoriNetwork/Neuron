# # 1. need  flask app
# # 2. a memory stucture of all of the neurons by timestamp when we last heard from them
# # 3. have some rest endpoints one of them is checkin  other is to connect 
from flask import Flask, request, jsonify
import time
import sqlite3

app = Flask(__name__)

# Initialize the database (this runs once at startup)
def init_db():
    conn = sqlite3.connect('peers.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS peers (
            peer_id TEXT PRIMARY KEY,
            last_seen REAL
        )
    ''')
    conn.commit()
    conn.close()

# Function to save peer check-in data to the database
def save_peer_checkin(peer_id, timestamp):
    conn = sqlite3.connect('peers.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO peers (peer_id, last_seen) VALUES (?, ?)', (peer_id, timestamp))
    conn.commit()
    conn.close()

# Function to get a peer's last check-in time
def get_peer_last_seen(peer_id):
    conn = sqlite3.connect('peers.db')
    cursor = conn.cursor()
    cursor.execute('SELECT last_seen FROM peers WHERE peer_id = ?', (peer_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return None

# Function to list all peers
def get_all_peers():
    conn = sqlite3.connect('peers.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM peers')
    peers = cursor.fetchall()
    conn.close()
    return peers

# Endpoint to check in a peer (saves peer and timestamp to database)
@app.route('/checkin', methods=['POST'])
def check_in():
    peer_data = request.get_json()
    peer_id = peer_data['peer_id']
    timestamp = time.time()
    
    # Save the peer's ID and timestamp to the database
    save_peer_checkin(peer_id, timestamp)
    return jsonify({"status": "checked in", "peer_id": peer_id, "timestamp": timestamp})

# Endpoint to connect to a peer (fetches last check-in time from database)
@app.route('/connect', methods=['POST'])
def connect_peer():
    peer_data = request.get_json()
    peer_id = peer_data['peer_id']
    
    # Get the last time we heard from the peer
    last_seen = get_peer_last_seen(peer_id)
    if last_seen:
        return jsonify({"status": "connected", "last_seen": last_seen})
    else:
        return jsonify({"status": "peer not found"}), 404

# Endpoint to list all peers and their last check-in times
@app.route('/peers', methods=['GET'])
def list_peers():
    peers = get_all_peers()
    return jsonify({peer[0]: peer[1] for peer in peers})

if __name__ == '__main__':
    init_db()  # Initialize the database when the app starts
    app.run(debug=True, host='0.0.0.0', port=51820)

# list peer
# curl http://188.166.4.120:51820/peers

# checkin
# curl -X POST http://188.166.4.120:51820/checkin -H "Content-Type: application/json" -d '{"peer_id": "peer1"}'

# connect
# curl -X POST http://188.166.4.120:51820/connect -H "Content-Type: application/json" -d '{"peer_id": "peer2"}'
