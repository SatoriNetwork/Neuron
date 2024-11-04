'''
todo:
    provide unique ip address that a peer can use as it's id as a separate endpoint
        peer logic:
            always ask for unique ip on startup before checking in with PeerServer
    remove stale peers (last_seen > 1 hour) (30 minute thread, purging peers by last_seen > 1 hour + 1 minute)
        remove stale connections too
        remove stale publications and subscriptions too
    accept a list of subscription and publication datastreams, save to a table by peer_id
        add endpoint for updating subscriptions and publications (reuse checkin endpoint?)
    connect peers together based on requests for datastreams (connect peer to publisher peer first, subscriber of desired datastream second)
        - if peer is already connected to publisher, connect to one of the publisher subscribers they are not already connected to
        - if the publisher already has too many direct connections, connect to a subscriber of the publisher 
        - (don't want to overload any one peer 200 max)
'''
from flask import Flask, request, jsonify
import time
import sqlite3
from collections import defaultdict
import json
import threading

class PeerServer:
    def __init__(self):
        self.app = Flask(__name__)
        self.peer_connections = defaultdict(set)
        self._init_routes()
        self._init_db()
        self._load_connections_from_db()
        self._start_cleanup_thread()

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
        # Publications table - modified to handle multiple streams per peer
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS publications (
                peer_id TEXT,
                stream TEXT,
                created_at REAL,
                PRIMARY KEY (peer_id, stream),
                FOREIGN KEY (peer_id) REFERENCES peers (peer_id)
            )
        ''')

         # Subscriptions table - modified to handle multiple streams per peer
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                peer_id TEXT,
                stream TEXT,
                created_at REAL,
                PRIMARY KEY (peer_id, stream),
                FOREIGN KEY (peer_id) REFERENCES peers (peer_id)
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
    
    def _start_cleanup_thread(self):
        """Start background thread for cleaning up stale peers and connections"""
        def cleanup_loop():
            while True:
                self._cleanup_stale_data()
                time.sleep(1800)  # Run every 30 minutes

        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()

    def _cleanup_stale_data(self):
        """Remove stale peers, connections, publications and subscriptions"""
        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        
        # Calculate cutoff time (1 hour ago)
        cutoff_time = time.time() - 3600
        
        try:
            # Get stale peer IDs
            cursor.execute('SELECT peer_id FROM peers WHERE last_seen < ?', (cutoff_time,))
            stale_peers = [row[0] for row in cursor.fetchall()]
            
            # Remove stale connections
            cursor.execute('''
                DELETE FROM connections 
                WHERE (from_peer IN (SELECT peer_id FROM peers WHERE last_seen < ?) 
                OR to_peer IN (SELECT peer_id FROM peers WHERE last_seen < ?))
            ''', (cutoff_time, cutoff_time))
            
            # Remove stale publications and subscriptions
            cursor.execute('DELETE FROM publications WHERE peer_id IN (SELECT peer_id FROM peers WHERE last_seen < ?)', (cutoff_time,))
            cursor.execute('DELETE FROM subscriptions WHERE peer_id IN (SELECT peer_id FROM peers WHERE last_seen < ?)', (cutoff_time,))
            
            # Remove stale peers
            cursor.execute('DELETE FROM peers WHERE last_seen < ?', (cutoff_time,))
            
            conn.commit()
            
            # Update in-memory connections
            for peer in stale_peers:
                if peer in self.peer_connections:
                    del self.peer_connections[peer]
                    
        except Exception as e:
            print(f"Error during cleanup: {e}")
            conn.rollback()
        finally:
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
        """Handle peer check-in/heartbeat with publication and subscription updates"""
        data = request.get_json()
        peer_id = data['peer_id']  # This is now the WireGuard public key
        timestamp = time.time()
        wireguard_config = data.get('wireguard_config')
        publications = data.get('publications', [])
        subscriptions = data.get('subscriptions', [])
        
        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        
        try:
            # Update peer information
            cursor.execute(
                'INSERT OR REPLACE INTO peers (peer_id, last_seen, wireguard_config) VALUES (?, ?, ?)',
                (peer_id, timestamp, json.dumps(wireguard_config))
            )
            
            # Update publications
            cursor.execute('DELETE FROM publications WHERE peer_id = ?', (peer_id,))
            for stream in publications:
                cursor.execute(
                    'INSERT INTO publications (peer_id, stream, created_at) VALUES (?, ?, ?)',
                    (peer_id, stream, timestamp)
                )
            
            # Update subscriptions
            cursor.execute('DELETE FROM subscriptions WHERE peer_id = ?', (peer_id,))
            for stream in subscriptions:
                cursor.execute(
                    'INSERT INTO subscriptions (peer_id, stream, created_at) VALUES (?, ?, ?)',
                    (peer_id, stream, timestamp)
                )
            
            conn.commit()
            
            return jsonify({
                "status": "checked in",
                "peer_id": peer_id,
                "timestamp": timestamp,
                "publications": publications,
                "subscriptions": subscriptions
            })
            
        except Exception as e:
            conn.rollback()
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
        finally:
            conn.close()

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
                return jsonify({
                    "status": "error",
                    "message": "One or both peers not found or missing WireGuard config"
                }), 400

        to_peer_config = json.loads(to_peer_result[0])
        from_peer_config = json.loads(from_peer_result[0])

        # Verify WireGuard configs contain required fields
        required_fields = ['public_key', 'allowed_ips', 'endpoint']
        if not all(field in to_peer_config for field in required_fields) or \
            not all(field in from_peer_config for field in required_fields):
            return jsonify({
                "status": "error",
                "message": "Invalid WireGuard configuration"
            }), 400
        
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
        """Get list of all peers with their publications and subscriptions"""
        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT p.peer_id, p.last_seen, p.wireguard_config,
                       GROUP_CONCAT(DISTINCT pub.stream) as publications,
                       GROUP_CONCAT(DISTINCT sub.stream) as subscriptions
                FROM peers p
                LEFT JOIN publications pub ON p.peer_id = pub.peer_id
                LEFT JOIN subscriptions sub ON p.peer_id = sub.peer_id
                GROUP BY p.peer_id
            ''')
            peers = cursor.fetchall()
            
            peer_list = []
            for peer in peers:
                peer_id, last_seen, wireguard_config, publications, subscriptions = peer
                peer_info = {
                    "peer_id": peer_id,
                    "last_seen": last_seen,
                    "last_seen_readable": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen)),
                    "wireguard_config": json.loads(wireguard_config) if wireguard_config else None,
                    "connected_peers": list(self.peer_connections[peer_id]),
                    "publications": publications.split(',') if publications else [],
                    "subscriptions": subscriptions.split(',') if subscriptions else []
                }
                peer_list.append(peer_info)
                
            return jsonify({
                "status": "success",
                "peers": peer_list,
                "total_peers": len(peer_list)
            })
            
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
        finally:
            conn.close()
            
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
