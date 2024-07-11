import socket
import json
from cryptography.fernet import Fernet

# Generate a key for encryption
key = Fernet.generate_key()
cipher = Fernet(key)


def send_message(ipv6_address, port, message):
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    encrypted_message = cipher.encrypt(message.encode())
    sock.sendto(encrypted_message, (ipv6_address, port))


def receive_message(port):
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.bind(('::', port))
    while True:
        data, addr = sock.recvfrom(1024)
        decrypted_message = cipher.decrypt(data).decode()
        print(f"Received message from {addr}: {decrypted_message}")


ipv6 = "fc54:08ab:ba2d:61dd:8297:6192:6e62:8810"
# Example usage
send_message(ipv6, 26041, "Hello, Peer!")
receive_message(26041)
