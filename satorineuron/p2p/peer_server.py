from flask import Flask, request, jsonify
import time
import sqlite3
from collections import defaultdict
import json

class PeerServer:
    def __init__(self):
        self.app = Flask(__name__)
        self.peer_connections = defaultdict(set)
        self._init_routes()
        self._init_db()
        self._load_connections_from_db()

    def _init_db(self):
        """Initialize SQLite database with peers and connections tables"""
        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        
        # Peers table for storing peer information
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS peers (
                peer_id TEXT PRIMARY KEY,
                last_seen REAL,
                wireguard_config TEXT
            )
        ''')
        
        # Connections table for storing peer connections
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS connections (
                from_peer TEXT,
                to_peer TEXT,
                connected_at REAL,
                active BOOLEAN,
                PRIMARY KEY (from_peer, to_peer),
                FOREIGN KEY (from_peer) REFERENCES peers (peer_id),
                FOREIGN KEY (to_peer) REFERENCES peers (peer_id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def _load_connections_from_db(self):
        """Load existing connections from database into memory"""
        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        cursor.execute('SELECT from_peer, to_peer FROM connections WHERE active = 1')
        connections = cursor.fetchall()
        conn.close()

        # Reset in-memory connections
        self.peer_connections = defaultdict(set)
        
        # Rebuild in-memory connections from database
        for from_peer, to_peer in connections:
            self.peer_connections[from_peer].add(to_peer)

    def _init_routes(self):
        """Initialize Flask routes"""
        self.app.route('/checkin', methods=['POST'])(self.check_in)
        self.app.route('/connect', methods=['POST'])(self.connect_peer)
        self.app.route('/list_peers', methods=['GET'])(self.list_peers)
        self.app.route('/list_connections', methods=['GET'])(self.list_connections)
        self.app.route('/disconnect', methods=['POST'])(self.disconnect_peer)

    def check_in(self):
        """Handle peer check-in/heartbeat"""
        data = request.get_json()
        peer_id = data['peer_id']
        timestamp = time.time()
        wireguard_config = data.get('wireguard_config')
        
        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO peers (peer_id, last_seen, wireguard_config) VALUES (?, ?, ?)',
            (peer_id, timestamp, json.dumps(wireguard_config))
        )
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "checked in",
            "peer_id": peer_id,
            "timestamp": timestamp
        })

    def connect_peer(self):
        """Handle peer connection requests"""
        data = request.get_json()
        from_peer = data['from_peer']
        to_peer = data['to_peer']

        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        
        # Get peer information
        cursor.execute('SELECT wireguard_config FROM peers WHERE peer_id = ?', (to_peer,))
        to_peer_result = cursor.fetchone()
        cursor.execute('SELECT wireguard_config FROM peers WHERE peer_id = ?', (from_peer,))
        from_peer_result = cursor.fetchone()
        
        if not (to_peer_result and from_peer_result):
            conn.close()
            return jsonify({"status": "error", "message": "peer not found"}), 400

        to_peer_config = json.loads(to_peer_result[0])
        from_peer_config = json.loads(from_peer_result[0])

        # Record the connection in database
        timestamp = time.time()
        cursor.execute('''
            INSERT OR REPLACE INTO connections 
            (from_peer, to_peer, connected_at, active) 
            VALUES (?, ?, ?, 1)
        ''', (from_peer, to_peer, timestamp))
        
        # Record the reverse connection as well (bidirectional)
        cursor.execute('''
            INSERT OR REPLACE INTO connections 
            (from_peer, to_peer, connected_at, active) 
            VALUES (?, ?, ?, 1)
        ''', (to_peer, from_peer, timestamp))
        
        conn.commit()
        conn.close()

        # Update in-memory connections
        self.peer_connections[from_peer].add(to_peer)
        self.peer_connections[to_peer].add(from_peer)

        return jsonify({
            "status": "connected",
            "from_peer": from_peer,
            "to_peer": to_peer,
            "from_peer_config": from_peer_config,
            "to_peer_config": to_peer_config,
            "connected_at": timestamp
        })

    def disconnect_peer(self):
        """Handle peer disconnection requests"""
        data = request.get_json()
        from_peer = data['from_peer']
        to_peer = data['to_peer']

        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        
        # Mark connections as inactive
        cursor.execute('''
            UPDATE connections 
            SET active = 0 
            WHERE (from_peer = ? AND to_peer = ?) OR (from_peer = ? AND to_peer = ?)
        ''', (from_peer, to_peer, to_peer, from_peer))
        
        conn.commit()
        conn.close()

        # Update in-memory connections
        self.peer_connections[from_peer].discard(to_peer)
        self.peer_connections[to_peer].discard(from_peer)

        return jsonify({
            "status": "disconnected",
            "from_peer": from_peer,
            "to_peer": to_peer
        })

    def list_peers(self):
        """Get list of all peers and their last seen timestamps"""
        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        cursor.execute('SELECT peer_id, last_seen, wireguard_config FROM peers')
        peers = cursor.fetchall()
        conn.close()
        
        peer_list = []
        for peer in peers:
            peer_id, last_seen, wireguard_config = peer
            peer_info = {
                "peer_id": peer_id,
                "last_seen": last_seen,
                "last_seen_readable": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen)),
                "wireguard_config": json.loads(wireguard_config) if wireguard_config else None,
                "connected_peers": list(self.peer_connections[peer_id])
            }
            peer_list.append(peer_info)
            
        return jsonify({
            "status": "success",
            "peers": peer_list,
            "total_peers": len(peer_list)
        })

    def list_connections(self):
        """Get list of all active connections"""
        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT from_peer, to_peer, connected_at 
            FROM connections 
            WHERE active = 1
        ''')
        connections = cursor.fetchall()
        conn.close()

        connection_list = []
        for from_peer, to_peer, connected_at in connections:
            connection_info = {
                "from_peer": from_peer,
                "to_peer": to_peer,
                "connected_at": connected_at,
                "connected_at_readable": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(connected_at))
            }
            connection_list.append(connection_info)

        return jsonify({
            "status": "success",
            "connections": connection_list,
            "total_connections": len(connection_list)
        })

    def run(self, host='0.0.0.0', port=51820):
        self.app.run(host=host, port=port)

if __name__ == '__main__':
    server = PeerServer()
    server.run()
