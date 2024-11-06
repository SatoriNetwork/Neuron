# '''
# Next step:
#      the server should remember who is connected to who

# '''
# from flask import Flask, request, jsonify
# import time
# import sqlite3
# from collections import defaultdict
# import json

# class PeerServer:
#     def __init__(self):
#         self.app = Flask(__name__)
#         self.peer_connections = defaultdict(set)
#         self._init_routes()
#         self._init_db()

#     # unused?
#     #def _save_peer_checkin(self, peer_id, timestamp, wireguard_config=None):
#     #    conn = sqlite3.connect('peers.db')
#     #    cursor = conn.cursor()
#     #    if wireguard_config:
#     #        cursor.execute(
#     #            'INSERT OR REPLACE INTO peers (peer_id, last_seen, wireguard_config) VALUES (?, ?, ?)', 
#     #            (peer_id, timestamp, json.dumps(wireguard_config))
#     #        )
#     #    else:
#     #        cursor.execute(
#     #            'UPDATE peers SET last_seen = ? WHERE peer_id = ?',
#     #            (timestamp, peer_id)
#     #        )
#     #    conn.commit()
#     #    conn.close()
    
#     def _init_db(self):
#         """Initialize SQLite database"""
#         conn = sqlite3.connect('peers.db')
#         cursor = conn.cursor()
#         cursor.execute('''
#             CREATE TABLE IF NOT EXISTS peers (
#                 peer_id TEXT PRIMARY KEY,
#                 last_seen REAL,
#                 wireguard_config TEXT
#             )
#         ''')
#         conn.commit()
#         conn.close()

#     def _init_routes(self):
#         """Initialize Flask routes"""
#         self.app.route('/checkin', methods=['POST'])(self.check_in)
#         self.app.route('/connect', methods=['POST'])(self.connect_peer)
#         self.app.route('/list_peers', methods=['GET'])(self.list_peers)
    # def check_in(self):
    #     """Handle peer check-in/heartbeat with publication and subscription updates"""
    #     # print("Received checkin request with payload:", request.get_data().decode('utf-8'))
    #     data = request.get_json()
    #     peer_id = data.get('peer_id')  # This is now the WireGuard public key
    #     if peer_id is None:
    #         return jsonify({"status": "error", "message": "Missing peer_id"}), 400
    #     timestamp = time.time()
    #     wireguard_config = data.get('wireguard_config')
    #     publications = data.get('publications', [])
    #     subscriptions = data.get('subscriptions', [])
        
    #     conn = sqlite3.connect('peers.db')
    #     cursor = conn.cursor()
    #     try:
    #         # Update peer information
    #         cursor.execute(
    #             'INSERT OR REPLACE INTO peers (peer_id, last_seen, wireguard_config) VALUES (?, ?, ?)',
    #             (peer_id, timestamp, json.dumps(wireguard_config))
    #         )
            
    #         # Update publications
    #         cursor.execute('DELETE FROM publications WHERE peer_id = ?', (peer_id,))
    #         for stream in publications:
    #             cursor.execute(
    #                 'INSERT INTO publications (peer_id, stream, created_at) VALUES (?, ?, ?)',
    #                 (peer_id, stream, timestamp)
    #             )
            
    #         # Update subscriptions
    #         cursor.execute('DELETE FROM subscriptions WHERE peer_id = ?', (peer_id,))
    #         for stream in subscriptions:
    #             cursor.execute(
    #                 'INSERT INTO subscriptions (peer_id, stream, created_at) VALUES (?, ?, ?)',
    #                 (peer_id, stream, timestamp)
    #             )
            
    #         conn.commit()
            
    #         return jsonify({
    #             "status": "checked in",
    #             "peer_id": peer_id,
    #             "timestamp": timestamp,
    #             "publications": publications,
    #             "subscriptions": subscriptions
    #         })
            
    #     except Exception as e:
    #         conn.rollback()
    #         return jsonify({
    #             "status": "error",
    #             "message": str(e)
    #         }), 500
    #     finally:
    #         conn.close()

#     def connect_peer(self):
#         """Handle peer connection requests"""
#         data = request.get_json()
#         from_peer = data['from_peer']
#         to_peer = data['to_peer']

#         # Get peer information
#         conn = sqlite3.connect('peers.db')
#         cursor = conn.cursor()
#         cursor.execute('SELECT wireguard_config FROM peers WHERE peer_id = ?', (to_peer,))
#         to_peer_result = cursor.fetchone()
#         cursor.execute('SELECT wireguard_config FROM peers WHERE peer_id = ?', (from_peer,))
#         from_peer_result = cursor.fetchone()
#         conn.close()

#         if not (to_peer_result and from_peer_result):
#             return jsonify({"status": "error", "message": "peer not found"}), 400

#         to_peer_config = json.loads(to_peer_result[0])
#         from_peer_config = json.loads(from_peer_result[0])

#         # Record the connection
#         self.peer_connections[from_peer].add(to_peer)
#         self.peer_connections[to_peer].add(from_peer)

#         return jsonify({
#             "status": "connected",
#             "from_peer": from_peer,
#             "to_peer": to_peer,
#             "from_peer_config": from_peer_config,
#             "to_peer_config": to_peer_config
#         })

#     def list_peers(self):
#         """Get list of all peers and their last seen timestamps"""
#         conn = sqlite3.connect('peers.db')
#         cursor = conn.cursor()
#         cursor.execute('SELECT peer_id, last_seen, wireguard_config FROM peers')
#         peers = cursor.fetchall()
#         conn.close()
#         peer_list = []
#         for peer in peers:
#             peer_id, last_seen, wireguard_config = peer
#             peer_info = {
#                 "peer_id": peer_id,
#                 "last_seen": last_seen,
#                 "last_seen_readable": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen)),
#                 "wireguard_config": json.loads(wireguard_config) if wireguard_config else None
#             }
#             peer_list.append(peer_info)
#         return jsonify({
#             "status": "success",
#             "peers": peer_list,
#             "total_peers": len(peer_list)
#         })


#     def run(self, host='0.0.0.0', port=51820):
#         self.app.run(host=host, port=port)

# if __name__ == '__main__':
#     server = PeerServer()
#     server.run()
