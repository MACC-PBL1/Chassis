import requests
import socket
import logging
import atexit
import os
from typing import Optional
import random
import base64

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
                    "HTTP": f"http://{ip_address}:{port}{health_path}",
                    "Interval": "10s",
                    "DeregisterCriticalServiceAfter": "1m",
                    "Status": "passing"
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