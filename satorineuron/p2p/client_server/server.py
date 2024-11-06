# list peer
# curl http://188.166.4.120:51820/peers

# checkin
# curl -X POST http://188.166.4.120:51820/checkin -H "Content-Type: application/json" -d '{"peer_id": "peer1"}'

# connect
# curl -X POST http://188.166.4.120:51820/connect -H "Content-Type: application/json" -d '{"peer_id": "peer2"}'
'''Adding swap can help provide additional virtual memory when RAM is exhausted. Here’s how to create a 1GB swap file:
dd if=/dev/zero of=/swapfile bs=1M count=1024
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile'''
from flask import Flask, request, jsonify
import time
import sqlite3
from collections import defaultdict

app = Flask(__name__)

# In-memory message queue for each peer
message_queues = defaultdict(list)
# Track active connections between peers
peer_connections = defaultdict(set)


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


def save_peer_checkin(peer_id, timestamp):
    conn = sqlite3.connect('peers.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR REPLACE INTO peers (peer_id, last_seen) VALUES (?, ?)', (peer_id, timestamp))
    conn.commit()
    conn.close()


def get_peer_last_seen(peer_id):
    conn = sqlite3.connect('peers.db')
    cursor = conn.cursor()
    cursor.execute('SELECT last_seen FROM peers WHERE peer_id = ?', (peer_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return None


def get_all_peers():
    conn = sqlite3.connect('peers.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM peers')
    peers = cursor.fetchall()
    conn.close()
    return peers


@app.route('/connect', methods=['POST'])
def connect_peer():
    data = request.get_json()
    from_peer = data['from_peer']
    to_peer = data['to_peer']

    # Check if target peer exists
    last_seen = get_peer_last_seen(to_peer)
    if not last_seen:
        return jsonify({"status": "peer not found"}), 404

    # If peer was seen in last 60 seconds, consider it active
    if time.time() - last_seen > 60:
        return jsonify({"status": "peer not active"}), 400

    # Establish bidirectional connection
    peer_connections[from_peer].add(to_peer)
    peer_connections[to_peer].add(from_peer)

    return jsonify({
        "status": "connected",
        "from_peer": from_peer,
        "to_peer": to_peer,
        "last_seen": last_seen
    })


@app.route('/disconnect', methods=['POST'])
def disconnect_peer():
    data = request.get_json()
    from_peer = data['from_peer']
    to_peer = data['to_peer']

    # Remove bidirectional connection
    peer_connections[from_peer].discard(to_peer)
    peer_connections[to_peer].discard(from_peer)

    return jsonify({
        "status": "disconnected",
        "from_peer": from_peer,
        "to_peer": to_peer
    })


@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.get_json()
    from_peer = data['from_peer']
    to_peer = data['to_peer']
    message = data['message']

    # Check if peers are connected
    if to_peer not in peer_connections[from_peer]:
        return jsonify({"status": "error", "message": "peers not connected"}), 400

    timestamp = time.time()
    message_queues[to_peer].append({
        'from': from_peer,
        'message': message,
        'timestamp': timestamp
    })

    return jsonify({
        "status": "message sent",
        "from": from_peer,
        "to": to_peer,
        "timestamp": timestamp
    })


@app.route('/receive_messages', methods=['POST'])
def receive_messages():
    data = request.get_json()
    peer_id = data['peer_id']
    messages = message_queues[peer_id]
    message_queues[peer_id] = []

    return jsonify({
        "status": "messages retrieved",
        "messages": messages
    })


@app.route('/checkin', methods=['POST'])
def check_in():
    peer_data = request.get_json()
    peer_id = peer_data['peer_id']
    timestamp = time.time()
    save_peer_checkin(peer_id, timestamp)
    return jsonify({"status": "checked in", "peer_id": peer_id, "timestamp": timestamp})


@app.route('/peers', methods=['GET'])
def list_peers():
    peers = get_all_peers()
    return jsonify({peer[0]: peer[1] for peer in peers})


@app.route('/connections', methods=['GET'])
def list_connections():
    peer_id = request.args.get('peer_id')
    if peer_id:
        connections = list(peer_connections[peer_id])
        return jsonify({
            "peer_id": peer_id,
            "connections": connections
        })
    return jsonify({"status": "error", "message": "peer_id required"}), 400


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=51820)
