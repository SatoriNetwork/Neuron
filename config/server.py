# server.py (Run on 10.0.0.1)
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('0.0.0.0', 51820))  # Listen on port 51820
server.listen(1)
print("Listening for incoming connections...")

conn, addr = server.accept()
print(f"Connected by {addr}")

data = conn.recv(1024)
print(f"Received message: {data.decode()}")
conn.close()
