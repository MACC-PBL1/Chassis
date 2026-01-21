import requests
import socket
import logging
import atexit
import os
from typing import Optional
import random
import base64

import requests
import socket
from typing import (
    Any,
    Optional,
)

import requests
import socket
import random
from typing import Optional

# class ConsulClient:
#     def __init__(self, host: str = "localhost", port: int = 8500):
#         self.base_url = f"http://{host}:{port}/v1"
    
#     def register(
#         self,
#         name: str,
#         service_id: Optional[str] = None,
#         address: Optional[str] = None,
#         port: Optional[int] = None,
#         tags: Optional[list] = None,
#         check_http: Optional[str] = None,
#         check_interval: str = "10s"
#     ):
#         """Register a service with Consul"""
#         service_id = service_id or f"{name}-{socket.gethostname()}"
#         address = address or socket.gethostbyname(socket.gethostname())
        
#         payload = {
#             "ID": service_id,
#             "Name": name,
#             "Address": address,
#         }
        
#         if port:
#             payload["Port"] = port
#         if tags:
#             payload["Tags"] = tags
#         if check_http:
#             payload["Check"] = {
#                 "HTTP": check_http,
#                 "Interval": check_interval
#             }
        
#         response = requests.put(
#             f"{self.base_url}/agent/service/register",
#             json=payload
#         )
#         response.raise_for_status()
#         return service_id
    
#     def deregister(self, service_id: str):
#         """Deregister a service from Consul"""
#         response = requests.put(
#             f"{self.base_url}/agent/service/deregister/{service_id}"
#         )
#         response.raise_for_status()
    
#     def get_service_url(self, name: str) -> Optional[str]:
#         """Get a random healthy service instance URL"""
#         response = requests.get(
#             f"{self.base_url}/health/service/{name}",
#             params={"passing": "true"}
#         )
#         response.raise_for_status()
        
#         services = response.json()
#         if not services:
#             return None
        
#         service = random.choice(services)["Service"]
#         tags = service.get("Tags", [])
#         scheme = "https" if "tls" in tags or "https" in tags else "http"
        
#         return f"{scheme}://{service['Address']}:{service['Port']}"
    
# # Initialize client
# client = ConsulClient(host="localhost", port=8500)

# # Register a service
# service_id = client.register(
#     name="my-api",
#     port=8080,
#     tags=["api", "v1"],
#     check_http="http://localhost:8080/health"
# )

# # Get a random instance URL
# url = client.get_service_url("my-api")
# print(url)  # http://192.168.1.10:8080

# # Deregister when shutting down
# client.deregister(service_id)

class ConsulClient:
    def __init__(
        self, 
        logger: logging.Logger, 
        consul_host: Optional[str] = None, 
        consul_port: int = 8500
    ) -> None:
        self._logger = logger
        self._consul_host = consul_host or os.getenv('CONSUL_HOST', 'consul')
        self._consul_port = consul_port
        self._service_id: Optional[str] = None

    def register_service(self, service_name: str, port: int, health_path: str = "/health") -> None:
        try:
            if not health_path.startswith("/"):
                health_path = "/" + health_path
            
            hostname = socket.gethostname()
            ip_address = os.getenv("HOST_IP", socket.gethostbyname(hostname))
            port = int(os.getenv("HOST_PORT", port))
            
            self._service_id = f"{service_name}-{hostname}"

            payload = {
                "ID": self._service_id,
                "Name": service_name,
                "Address": ip_address,
                "Port": port,
                "Check": {
                    "HTTP": f"http{"s" if port == 443 else ""}://{ip_address}:{port}{health_path}",
                    "Interval": "10s",
                    "DeregisterCriticalServiceAfter": "1m",
                    "Status": "passing",
                    "TLSSkipVerify": True
                }
            }

            url = f"http://{self._consul_host}:{self._consul_port}/v1/agent/service/register"
            res = requests.put(url, json=payload, timeout=2)
            
            if res.status_code == 200:
                self._logger.info(f"[LOG:CHASSIS:CONSUL] - Service '{service_name}' registered successfully as '{self._service_id}'")
                atexit.register(self.deregister_service)
            else:
                self._logger.error(f"[LOG:CHASSIS:CONSUL] - Failed to register: Reason={res.text}", exc_info=True)

        except Exception as e:
            self._logger.error(f"[LOG:CHASSIS:CONSUL] - Connection failed: Reason={e}", exc_info=True)

    def deregister_service(self) -> None:
        if not self._service_id:
            return
        try:
            url = f"http://{self._consul_host}:{self._consul_port}/v1/agent/service/deregister/{self._service_id}"
            requests.put(url, timeout=2)
            self._logger.info(f"[LOG:CHASSIS:CONSUL] - Service '{self._service_id}' deregistered.")
        except Exception as e:
            self._logger.warning(f"[LOG:CHASSIS:CONSUL] - Error during deregistration: Reason={e}", exc_info=True)
            
    def get_service_url(self, service_name: str) -> Optional[str]:
        try:
            url = f"http://{self._consul_host}:{self._consul_port}/v1/health/service/{service_name}"
            res = requests.get(url, params={"passing": "true"}, timeout=11)
            
            if res.status_code == 200:
                instances = res.json()
                if not instances:
                    self._logger.warning(f"[LOG:CHASSIS:CONSUL] - No instances found for '{service_name}'")
                    return None

                target = random.choice(instances)
                service_ip = target["Service"]["Address"]
                service_port = target["Service"]["Port"]
                
                return f"http://{service_ip}:{service_port}"
            else:
                self._logger.error(f"[LOG:CHASSIS:CONSUL] - Error finding service: {res.text}")
                return None

        except Exception as e:
            self._logger.error(f"[LOG:CHASSIS:CONSUL] - Discovery failed: Reason={e}", exc_info=True)
            return None