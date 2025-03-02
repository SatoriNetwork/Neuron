import asyncio
from satorineuron import config
from satorilib.datamanager import DataServer
from satorilib.wallet.evrmore.identity import EvrmoreIdentity 

import socket
import subprocess
import platform

# This should move out of here
def check_ipv6_capability():
    """Check if the system has IPv6 capability using multiple methods."""
    results = {
        "socket_support": False,
        "loopback_available": False,
        "external_connectivity": False
    }
    try:
        socket.has_ipv6 = False
        socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        results["socket_support"] = True
        print("Socket IPv6 support: Available")
    except (socket.error, AttributeError):
        print("Socket IPv6 support: Not available")

    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.connect(("::1", 0))
        s.close()
        results["loopback_available"] = True
        print("IPv6 loopback: Available")
    except (socket.error, OSError):
        print("IPv6 loopback: Not available")
    
    system = platform.system().lower()
    
    if system == "linux" or system == "darwin":  # Linux or macOS
        try:
            output = subprocess.check_output(["ip", "-6", "addr"], 
                                            stderr=subprocess.STDOUT,
                                            universal_newlines=True)
            if "inet6" in output:
                print("IPv6 addresses configured: Yes")
            else:
                print("IPv6 addresses configured: No")
        except (subprocess.SubprocessError, FileNotFoundError):
            print("Couldn't check IPv6 configuration via 'ip' command")
    
    elif system == "windows":
        try:
            output = subprocess.check_output(["ipconfig"], 
                                            stderr=subprocess.STDOUT,
                                            universal_newlines=True)
            if "IPv6 Address" in output:
                print("IPv6 addresses configured: Yes")
            else:
                print("IPv6 addresses configured: No")
        except subprocess.SubprocessError:
            print("Couldn't check IPv6 configuration via 'ipconfig' command")
    
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("2001:4860:4860::8888", 53))
        s.close()
        results["external_connectivity"] = True
        print("External IPv6 connectivity: Available")
    except (socket.error, OSError):
        print("External IPv6 connectivity: Not available")
    
    return results

async def runServerForever():
    ipv6 = False
    results = check_ipv6_capability()
    if results["socket_support"] and results["loopback_available"]:
        ipv6 = True

    if ipv6:
        serverIpv6 = DataServer('::', 24602, EvrmoreIdentity(config.walletPath('wallet.yaml')))
        await serverIpv6.startServer()
    else:
        serverIpv4 = DataServer('0.0.0.0', 24602, EvrmoreIdentity(config.walletPath('wallet.yaml')))
        await serverIpv4.startServer()

    await asyncio.Future()  

asyncio.run(runServerForever())