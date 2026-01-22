from typing import Optional
import requests
import os
import logging
import random

class ConsulClient:
    def __init__(self, consul_host: str, consul_port: int, logger: Optional[logging.Logger] = None, timeout: int = 2):
        """
        Args:
            consul_host: Consul server address (EC2_2 private IP)
            consul_port: Consul server port
            logger: Optional logger instance
            timeout: Request timeout in seconds
        """
        self._logger = logger or logging.getLogger(__name__)
        self.consul_host = consul_host
        self.consul_port = consul_port
        self.timeout = timeout
        self.service_id = None
        
    def register_service(
        self, 
        service_name: str, 
        ec2_address: str, 
        service_port: int = 443, 
        health_check_interval: str = "10s", 
    ) -> None:
        """
        Register microservice using EC2's external address (where HAProxy is).
        
        Args:
            service_name: Microservice name
            ec2_address: This EC2's IP/hostname
            service_port: External port
            health_check_interval: Health check interval
        """
        try:
            # Unique ID per instance
            self.service_id = f"{service_name}-{ec2_address.replace('.', '-')}"
            
            protocol = "https" if service_port == 443 else "http"
            
            payload = {
                "ID": self.service_id,
                "Name": service_name,
                "Address": ec2_address,
                "Port": service_port,
                "Check": {
                    "HTTP": f"{protocol}://{ec2_address}:{service_port}/{service_name}/health",
                    "Interval": health_check_interval,
                    "Timeout": "5s",
                    "Status": "passing",
                    "TLSSkipVerify": True
                }
            }
            
            url = f"http://{self.consul_host}:{self.consul_port}/v1/agent/service/register"
            res = requests.put(url, json=payload, timeout=self.timeout)
            
            if res.status_code == 200:
                self._logger.info(f"[LOG:CHASSIS:CONSUL] - Service '{service_name}' registered successfully as '{self.service_id}'")
            else:
                self._logger.error(f"[LOG:CHASSIS:CONSUL] - Failed to register: Reason={res.text}", exc_info=True)
                
        except Exception as e:
            self._logger.error(f"[LOG:CHASSIS:CONSUL] - Connection failed: Reason={e}", exc_info=True)
                
    def deregister_service(self) -> None:
        """Deregister on shutdown."""
        if not self.service_id:
            return
            
        try:
            url = f"http://{self.consul_host}:{self.consul_port}/v1/agent/service/deregister/{self.service_id}"
            requests.put(url, timeout=self.timeout)
            self._logger.info(f"[LOG:CHASSIS:CONSUL] - Service '{self.service_id}' deregistered.")
        except Exception as e:
            self._logger.warning(f"[LOG:CHASSIS:CONSUL] - Error during deregistration: Reason={e}", exc_info=True)
    
    def discover_service(self, service_name: str) -> Optional[tuple[str, int]]:
        """
        Discover a random healthy instance of a service.
        
        Returns:
            Tuple of (address, port) or None if no healthy instances
        """
        try:
            url = f"http://{self.consul_host}:{self.consul_port}/v1/health/service/{service_name}"
            res = requests.get(url, params={"passing": "true"}, timeout=self.timeout)
            
            if res.status_code == 200:
                instances = res.json()
                if not instances:
                    self._logger.warning(f"[LOG:CHASSIS:CONSUL] - No instances found for '{service_name}'")
                    return None

                target = random.choice(instances)
                service_address = "http://" + target["Service"]["Address"]
                service_port = target["Service"]["Port"]
                
                return service_address, service_port
            else:
                self._logger.error(f"[LOG:CHASSIS:CONSUL] - Error finding service: {res.text}")
                return None
                
        except Exception as e:
            self._logger.error(f"[LOG:CHASSIS:CONSUL] - Discovery failed: Reason={e}", exc_info=True)
            return None

CONSUL_CLIENT = ConsulClient(
    consul_host=os.getenv("CONSUL_HOST", "localhost"),
    consul_port=int(os.getenv("CONSUL_PORT", 8500)),
)