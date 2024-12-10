import unittest
import time
from satorineuron.p2p.client_server.client import MessageClient, RateLimitConfig, MessageStats


class TestMessageClient(unittest.TestCase):

    def setUp(self):
        self.server_url = "http://188.166.4.120:51820"
        self.client_id = "test-client"
        self.client = MessageClient(self.server_url, self.client_id)

    def test_update_message_stats(self):
        peer_id = "test-peer"
        self.client.rate_limit_config = RateLimitConfig(
            window_size=10, message_limit=5)

        # Test within limit
        for i in range(5):
            result = self.client.update_message_stats(peer_id, time.time())
            self.assertFalse(result)

        # Test exceeding limit
        result = self.client.update_message_stats(peer_id, time.time())
        self.assertTrue(result)

        # Test message count
        self.assertEqual(self.client.peer_stats[peer_id].total_messages, 6)

    def test_add_to_message_history(self):
        message = {"from": "peer1", "message": "Hello"}
        self.client.add_to_message_history(message)

        self.assertEqual(len(self.client.message_history), 1)
        self.assertIn("received_at", self.client.message_history[0])

        # Test max history limit
        self.client.max_history = 2
        self.client.add_to_message_history({"from": "peer2", "message": "Hi"})
        self.client.add_to_message_history({"from": "peer3", "message": "Hey"})

        self.assertEqual(len(self.client.message_history), 2)
        self.assertEqual(self.client.message_history[0]["from"], "peer2")

    def test_get_peer_stats(self):
        peer_id = "test-peer"
        self.client.peer_stats[peer_id] = MessageStats()
        self.client.peer_stats[peer_id].total_messages = 10
        self.client.peer_stats[peer_id].messages = [
            time.time() for _ in range(5)]

        stats = self.client.get_peer_stats(peer_id)

        self.assertEqual(stats["peer_id"], peer_id)
        self.assertEqual(stats["total_messages"], 10)
        self.assertEqual(stats["messages_in_window"], 5)
        self.assertEqual(stats["rate_limit"],
                         self.client.rate_limit_config.message_limit)

    def test_checkin(self):
        result = self.client.checkin()
        self.assertIsNotNone(result)
        self.assertIn('status', result)

    def test_connect_and_disconnect_peer(self):
        # First, create another client to connect to
        other_client_id = f"other-client-{int(time.time())}"
        other_client = MessageClient(self.server_url, other_client_id)
        other_client.checkin()

        # Test connection
        connect_result = self.client.connect_to_peer(other_client_id)
        self.assertIsNotNone(connect_result)
        self.assertIn(other_client_id, self.client.connected_peers)
        self.assertIn(other_client_id, self.client.peer_stats)

        # Test disconnection
        disconnect_result = self.client.disconnect_from_peer(other_client_id)
        self.assertIsNotNone(disconnect_result)
        self.assertNotIn(other_client_id, self.client.connected_peers)

    def test_connect_to_nonexistent_peer(self):
        nonexistent_peer = "nonexistent-peer"
        result = self.client.connect_to_peer(nonexistent_peer)
        self.assertIsNone(result)
        self.assertNotIn(nonexistent_peer, self.client.connected_peers)
        self.assertNotIn(nonexistent_peer, self.client.peer_stats)

    def test_multiple_connections(self):
        # Create multiple clients
        other_clients = [
            MessageClient(self.server_url,
                          f"other-client-{i}-{int(time.time())}")
            for i in range(3)
        ]
        for client in other_clients:
            client.checkin()

        # Connect to all clients
        for client in other_clients:
            result = self.client.connect_to_peer(client.client_id)
            self.assertIsNotNone(result)
            self.assertIn(client.client_id, self.client.connected_peers)

        # Verify the number of connections
        self.assertEqual(len(self.client.connected_peers), len(other_clients))

        # Disconnect from all clients
        for client in other_clients:
            result = self.client.disconnect_from_peer(client.client_id)
            self.assertIsNotNone(result)
            self.assertNotIn(client.client_id, self.client.connected_peers)

        # Verify all disconnected
        self.assertEqual(len(self.client.connected_peers), 0)

    def test_rate_limit_warning(self):
        peer_id = "test-peer"
        self.client.rate_limit_config = RateLimitConfig(
            window_size=10,
            message_limit=10,
            warning_threshold=0.7,
            warning_cooldown=5
        )

        # Send messages up to warning threshold
        for i in range(7):
            self.client.update_message_stats(peer_id, time.time())

        # This should trigger a warning
        result = self.client.update_message_stats(peer_id, time.time())
        self.assertFalse(result)  # Not exceeding limit yet
        self.assertGreater(
            self.client.peer_stats[peer_id].last_warning_time, 0)

        # Wait for cooldown
        time.sleep(5)

        # This should trigger another warning
        self.client.update_message_stats(peer_id, time.time())
        new_warning_time = self.client.peer_stats[peer_id].last_warning_time
        self.assertGreater(new_warning_time, 5)

    def test_show_message_history(self):
        # Add some messages to history
        self.client.add_to_message_history(
            {"from": "peer1", "message": "Hello"})
        self.client.add_to_message_history({"from": "peer2", "message": "Hi"})
        self.client.add_to_message_history(
            {"from": "peer1", "message": "How are you?"})

        # Capture print output
        import io
        import sys
        captured_output = io.StringIO()
        sys.stdout = captured_output

        # Test showing all messages
        self.client.show_message_history()
        output = captured_output.getvalue()
        self.assertIn("From peer1: Hello", output)
        self.assertIn("From peer2: Hi", output)
        self.assertIn("From peer1: How are you?", output)

        # Reset captured output
        captured_output.truncate(0)
        captured_output.seek(0)

        # Test showing messages from specific peer
        self.client.show_message_history("peer1")
        output = captured_output.getvalue()
        self.assertIn("From peer1: Hello", output)
        self.assertIn("From peer1: How are you?", output)
        self.assertNotIn("From peer2: Hi", output)

        # Restore stdout
        sys.stdout = sys.__stdout__


if __name__ == '__main__':
    unittest.main()
