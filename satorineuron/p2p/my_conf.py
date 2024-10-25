#!/usr/bin/env python3
import subprocess
import json
import re
import requests
from typing import Dict, Optional
import sys

class WireguardInfo:
    def __init__(self, interface: str = 'wg0'):
        self.interface = interface
        
    def _run_command(self, command: list) -> tuple[str, Optional[str]]:
        """Run a shell command and return stdout and stderr."""
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            return stdout.strip(), stderr.strip()
        except subprocess.CalledProcessError as e:
            return '', f"Error executing command: {e}"
        except Exception as e:
            return '', f"Unexpected error: {e}"

    def get_interface_address(self) -> str:
        """Get the IP address assigned to the WireGuard interface."""
        stdout, stderr = self._run_command(['ip', 'address', 'show', self.interface])
        
        if stderr:
            return f"Error: {stderr}"
            
        # Look for inet line in the output
        for line in stdout.split('\n'):
            if 'inet ' in line:
                # Extract the IP address using regex
                match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+/\d+)', line)
                if match:
                    return match.group(1)
        
        return "No IP address found"

    def get_wireguard_info(self) -> Dict:
        """Get WireGuard interface information."""
        stdout, stderr = self._run_command([ 'wg', 'show', self.interface])
        public_ip = WireguardInfo.get_public_ip(self)
        
        if stderr:
            return {'error': stderr}
            
        info = {
            # 'interface': self.interface,
            'public_key': '',
            'endpoint': f"{public_ip}:51820",
            'allowed_ips': self.get_interface_address().rsplit("/", 1)[0] + "/32",
            
        }
        
        current_peer = None
        
        for line in stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if 'public key' in line.lower() and ':' in line:
                if 'peer:' not in line.lower():
                    info['public_key'] = line.split(':')[1].strip()
                else:
                    current_peer = {'public_key': line.split(':')[1].strip()}
                    info['peers'].append(current_peer)
                    
            # elif 'listening port' in line.lower() and ':' in line:
            #     info['listening_port'] = line.split(':')[1].strip()
                
        return info

    def get_public_ip(self) -> str:
        """Get the public IP address using multiple services."""
        ip_services = [
            'https://api.ipify.org?format=json',
            'https://ifconfig.me/ip',
            'https://icanhazip.com'
        ]
        
        for service in ip_services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    if service.endswith('json'):
                        return response.json()['ip']
                    return response.text.strip()
            except:
                continue
                
        return "Could not determine public IP"

def main():
    # Create instance of WireguardInfo
    wg = WireguardInfo()
    
    # Get WireGuard information
    wg_info = wg.get_wireguard_info()
    
    # Get public IP
    # public_ip = wg.get_public_ip()
    
    # Combine all information
    full_info = {
        'wireguard_config': wg_info,
        # 'public_ip': public_ip
    }
    
    # Print formatted JSON output
    print(json.dumps(full_info, indent=2))

if __name__ == "__main__":
    main()
