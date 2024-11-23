from flask import Flask, request, jsonify
import time
import sqlite3
from collections import defaultdict
import json
import threading
import random

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
        
        # Modified stream_history table to better handle JSON stream IDs
        cursor.execute('''
            DROP TABLE IF EXISTS stream_history
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stream_history (
                peer_id TEXT,
                stream_id TEXT,
                cache_data TEXT,
                timestamp REAL,
                PRIMARY KEY (peer_id, stream_id)
            )
        ''')
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

        
        try:
            # Check if publications table needs updating
            cursor.execute("PRAGMA table_info(publications)")
            columns = {row[1] for row in cursor.fetchall()}
            
            if 'created_at' not in columns:
                print("Adding created_at column to publications table...")
                # Create temporary table with new schema
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS publications_new (
                        peer_id TEXT,
                        stream TEXT,
                        created_at REAL,
                        PRIMARY KEY (peer_id, stream),
                        FOREIGN KEY (peer_id) REFERENCES peers (peer_id)
                    )
                ''')
                
                # Copy data from old table to new table
                cursor.execute('''
                    INSERT OR REPLACE INTO publications_new (peer_id, stream, created_at)
                    SELECT peer_id, stream, ? FROM publications
                ''', (time.time(),))
                
                # Drop old table and rename new table
                cursor.execute('DROP TABLE publications')
                cursor.execute('ALTER TABLE publications_new RENAME TO publications')
            
            # Do the same for subscriptions table
            cursor.execute("PRAGMA table_info(subscriptions)")
            columns = {row[1] for row in cursor.fetchall()}
            
            if 'created_at' not in columns:
                print("Adding created_at column to subscriptions table...")
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subscriptions_new (
                        peer_id TEXT,
                        stream TEXT,
                        created_at REAL,
                        PRIMARY KEY (peer_id, stream),
                        FOREIGN KEY (peer_id) REFERENCES peers (peer_id)
                    )
                ''')
                
                cursor.execute('''
                    INSERT OR REPLACE INTO subscriptions_new (peer_id, stream, created_at)
                    SELECT peer_id, stream, ? FROM subscriptions
                ''', (time.time(),))
                
                cursor.execute('DROP TABLE subscriptions')
                cursor.execute('ALTER TABLE subscriptions_new RENAME TO subscriptions')
                
            
            conn.commit()
            print("Database schema updated successfully")
            
        except Exception as e:
            print(f"Error updating database schema: {e}")
            conn.rollback()
        finally:
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
        self.app.route('/get_unique_ip', methods=['GET'])(self.get_unique_ip)
        self.app.route('/checkin', methods=['POST'])(self.check_in)
        self.app.route('/connect', methods=['POST'])(self.connect_peer)
        self.app.route('/list_peers', methods=['GET'])(self.list_peers)
        self.app.route('/list_connections', methods=['GET'])(self.list_connections)
        self.app.route('/connect_datastream', methods=['POST'])(self.connect_datastream)
        self.app.route('/disconnect', methods=['POST'])(self.disconnect_peer)
        self.app.route('/get_cache', methods=['GET'])(self.get_cache)
        self.app.route('/update_cache', methods=['POST'])(self.update_cache)


    def update_cache(self):
        """Update the cache data for a given peer and stream"""
        try:
            data = request.get_json()
            peer_id = data.get('peer_id')
            stream_id = data.get('stream_id')
            cache = data.get('cache')
            
            conn = sqlite3.connect('peers.db')
            cursor = conn.cursor()
            
            try:
                # Update the stream_history table
                cursor.execute("""
                    INSERT OR REPLACE INTO stream_history 
                    (peer_id, stream_id, cache_data, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (peer_id, stream_id, json.dumps(cache), time.time()))
                
                conn.commit()
                return jsonify({"status": "success"})
                
            except Exception as e:
                conn.rollback()
                return jsonify({"status": "error", "message": str(e)}), 500
            finally:
                conn.close()
                
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # def get_cache(self):
    #     """Retrieve the cache data for a given stream"""
    #     try:
    #         stream_id = request.args.get('stream_id')
            
    #         conn = sqlite3.connect('peers.db')
    #         cursor = conn.cursor()
            
    #         try:
    #             # Fetch from stream_history table
    #             cursor.execute("""
    #                 SELECT cache_data 
    #                 FROM stream_history 
    #                 WHERE stream_id = ? 
    #                 ORDER BY timestamp DESC 
    #                 LIMIT 1
    #             """, (stream_id,))
                
    #             result = cursor.fetchone()
                
    #             if result:
    #                 return jsonify({
    #                     "status": "success",
    #                     "cache": json.loads(result[0])
    #                 })
    #             return jsonify({
    #                 "status": "success",
    #                 "cache": []
    #             })
                
    #         except Exception as e:
    #             return jsonify({"status": "error", "message": str(e)}), 500
    #         finally:
    #             conn.close()
                
    #     except Exception as e:
    #         return jsonify({"status": "error", "message": str(e)}), 500
    def get_cache(self):
        """Retrieve the cache data for a given stream"""
        try:
            # Get individual parameters instead of a JSON object
            source = request.args.get('source')
            author = request.args.get('author')
            stream = request.args.get('stream')
            target = request.args.get('target')
            
            # Construct stream identifier in a consistent format
            stream_id = json.dumps({
                "source": source,
                "author": author,
                "stream": stream,
                "target": target
            }, sort_keys=True)  # sort_keys ensures consistent ordering
            
            conn = sqlite3.connect('peers.db')
            cursor = conn.cursor()
            
            try:
                # Fetch from stream_history table
                cursor.execute("""
                    SELECT cache_data 
                    FROM stream_history 
                    WHERE stream_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """, (stream_id,))
                
                result = cursor.fetchone()
                
                if result:
                    return jsonify({
                        "status": "success",
                        "cache": json.loads(result[0])
                    })
                return jsonify({
                    "status": "success",
                    "cache": []
                })
                
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
            finally:
                conn.close()
                
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    def get_unique_ip(self):
        """Generate a unique IP address for a peer"""
        unique_ip = self._generate_unique_ip()
        return jsonify({"ip_address": unique_ip})

    def _generate_unique_ip(self):
        """Generate a unique IP address in the range 10.x.y.z with a /16 subnet"""
        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()

        while True:
            ip_address = f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
            cursor.execute("SELECT COUNT(*) FROM peers WHERE wireguard_config LIKE ?", (f"%{ip_address}%",))
            count = cursor.fetchone()[0]
            if count == 0:
                conn.close()
                return ip_address

        conn.close()

    def check_in(self):
        try:
            data = request.get_json()
            peer_id = data.get('peer_id')
            timestamp = time.time()
            wireguard_config = data.get('wireguard_config')
            publications = data.get('publications', [])
            subscriptions = data.get('subscriptions', [])
            cache = data.get('cache', {})
           
            
            conn = sqlite3.connect('peers.db')
            cursor = conn.cursor()
            # cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            try:
                # print("Updating peer info in database...")
                cursor.execute(
                    'INSERT OR REPLACE INTO peers (peer_id, last_seen, wireguard_config) VALUES (?, ?, ?)',
                    (peer_id, timestamp, json.dumps(wireguard_config))
                )
                
                # print("Updating publications...")
                cursor.execute('DELETE FROM publications WHERE peer_id = ?', (peer_id,))
                for stream in publications:
                    # print(f"Adding publication: {stream}")
                    cursor.execute(
                        'INSERT INTO publications (peer_id, stream, created_at) VALUES (?, ?, ?)',
                        (peer_id, stream, timestamp)
                    )
                
                # print("Updating subscriptions...")
                cursor.execute('DELETE FROM subscriptions WHERE peer_id = ?', (peer_id,))
                for stream in subscriptions:
                    cursor.execute(
                        'INSERT INTO subscriptions (peer_id, stream, created_at) VALUES (?, ?, ?)',
                        (peer_id, stream, timestamp)
                    )
                for stream_id, stream_data in cache.items():
                    cursor.execute(
                        '''
                        INSERT OR REPLACE INTO stream_history (stream_id, data, timestamp)
                        VALUES (?, ?, ?)
                        ''',
                        (stream_id, json.dumps(stream_data), timestamp)
                    )
                conn.commit()
                
                return jsonify({
                    "status": "checked in",
                    "peer_id": peer_id,
                    "timestamp": timestamp,
                    "publications": publications,
                    "subscriptions": subscriptions,
                    "cache_processed": True,
                })
                
            except Exception as e:
                print(f"Database error occurred: {str(e)}")
                conn.rollback()
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500
            finally:
                conn.close()
                
        except Exception as e:
            print(f"Request processing error: {str(e)}")
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

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
    
    def connect_datastream(self):
        data = request.get_json()
        return self.connect_peers_for_datastream(data['peer_id'], data['stream'])
    
    def connect_peers_for_datastream(self, requesting_peer_id, desired_stream):
        """Connect peers based on datastream requirements"""
        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        
        try:
            # Find publishers of the desired stream
            cursor.execute('''
                SELECT p.peer_id, COUNT(c.to_peer) as connection_count
                FROM peers p
                JOIN publications pub ON p.peer_id = pub.peer_id
                LEFT JOIN connections c ON p.peer_id = c.from_peer
                WHERE pub.stream = ? AND p.peer_id != ?
                GROUP BY p.peer_id
                ORDER BY connection_count ASC
            ''', (desired_stream, requesting_peer_id))
            publishers = cursor.fetchall()
            
            if not publishers:
                return {"status": "error", "message": "No publishers found for stream"}
            
            # Try to connect to a publisher directly if they have less than 200 connections
            for publisher_id, connection_count in publishers:
                if connection_count < 200:
                    # Check if already connected
                    if publisher_id not in self.peer_connections[requesting_peer_id]:
                        return self.connect_peer_internal(requesting_peer_id, publisher_id)
            
            # If all publishers are at capacity, find their subscribers
            cursor.execute('''
                SELECT s.peer_id, COUNT(c.to_peer) as connection_count
                FROM subscriptions s
                JOIN connections c ON s.peer_id = c.from_peer
                WHERE s.stream = ? 
                AND s.peer_id != ?
                AND EXISTS (
                    SELECT 1 FROM connections 
                    WHERE from_peer = s.peer_id 
                    AND to_peer IN (
                        SELECT peer_id FROM publications WHERE stream = ?
                    )
                )
                GROUP BY s.peer_id
                HAVING connection_count < 200
                ORDER BY connection_count ASC
            ''', (desired_stream, requesting_peer_id, desired_stream))
            
            subscribers = cursor.fetchall()
            
            if subscribers:
                subscriber_id, _ = subscribers[0]
                return self.connect_peer_internal(requesting_peer_id, subscriber_id)
                
            return {"status": "error", "message": "No available peers for connection"}
            
        finally:
            conn.close()

    def connect_peer_internal(self, from_peer, to_peer):
        """Internal method to handle peer connection"""
        conn = sqlite3.connect('peers.db')
        cursor = conn.cursor()
        
        try:
            # Get peer information
            cursor.execute('SELECT wireguard_config FROM peers WHERE peer_id = ?', (to_peer,))
            to_peer_result = cursor.fetchone()
            cursor.execute('SELECT wireguard_config FROM peers WHERE peer_id = ?', (from_peer,))
            from_peer_result = cursor.fetchone()
            
            if not (to_peer_result and from_peer_result):
                return {
                    "status": "error",
                    "message": "One or both peers not found"
                }

            to_peer_config = json.loads(to_peer_result[0])
            from_peer_config = json.loads(from_peer_result[0])
            
            # Record the connection
            timestamp = time.time()
            cursor.execute('''
                INSERT OR REPLACE INTO connections 
                (from_peer, to_peer, connected_at, active) 
                VALUES (?, ?, ?, 1)
            ''', (from_peer, to_peer, timestamp))
            
            cursor.execute('''
                INSERT OR REPLACE INTO connections 
                (from_peer, to_peer, connected_at, active) 
                VALUES (?, ?, ?, 1)
            ''', (to_peer, from_peer, timestamp))
            
            conn.commit()
            
            # Update in-memory connections
            self.peer_connections[from_peer].add(to_peer)
            self.peer_connections[to_peer].add(from_peer)
            
            return {
                "status": "connected",
                "from_peer": from_peer,
                "to_peer": to_peer,
                "from_peer_config": from_peer_config,
                "to_peer_config": to_peer_config,
                "connected_at": timestamp
            }
            
        finally:
            conn.close()
    
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
        self.app.run(host=host, port=port, debug=True)

if __name__ == '__main__':
    server = PeerServer()
    server.run()
