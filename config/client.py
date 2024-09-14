# client.py (Run on 10.0.0.2)
import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('10.0.0.1', 51820))  # Connect to 10.0.0.1 on port 51820
client.sendall(b'hello')
client.close()
