from typing import Optional
import consul

class ConsulClient:
    def __init__(self, consul_host: str, consul_port: int):
        """
        Args:
            consul_host: Consul server address (EC2_2 private IP)
        """
        self.consul = consul.Consul(host=consul_host, port=consul_port)
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
            use_https: Whether HAProxy uses HTTPS
        """
        # Unique ID per instance
        self.service_id = f"{service_name}-{ec2_address.replace('.', '-')}"
        
        protocol = "http"
        
        self.consul.agent.service.register(
            name=service_name,
            service_id=self.service_id,
            address=ec2_address,
            port=service_port,
            check={
                "http": f"{protocol}://{ec2_address}:{service_port}/{service_name}/health",
                "interval": health_check_interval,
                "timeout": "5s",
                "tls_skip_verify": True
            }
        )
                
    def deregister_service(self) -> None:
        """Deregister on shutdown."""
        if self.service_id:
            self.consul.agent.service.deregister(self.service_id)
    
    def discover_service(self, service_name: str) -> Optional[tuple[str, int]]:
        """
        Discover a random healthy instance of a service.
        
        Returns:
            Tuple of (address, port) or None if no healthy instances
        """
        import random
        
        _, services = self.consul.health.service(service_name, passing=True)
        if not services:
            return None
        
        service = random.choice(services)
        return service['Service']['Address'], service['Service']['Port']


# Usage
# if __name__ == "__main__":
#     client = ConsulClient(consul_host=os.getenv("CONSUL_HOST"))  # EC2_2 IP
    
#     SERVICE_NAME = os.getenv("SERVICE_NAME", "my-microservice")
#     EC2_ADDRESS = os.getenv("EC2_ADDRESS")  # This EC2's IP/hostname
    
#     try:
#         client.register_service(
#             service_name=SERVICE_NAME,
#             ec2_address=EC2_ADDRESS,
#             haproxy_port=443
#         )
        
#         # Discover microservice2 - returns [(ec2_3_ip, 443), ...]
#         addr, port = client.discover_service("microservice2")
#         response = requests.get(f"https://{addr}:{port}/api/endpoint", verify=False)
        
#     finally:
#         client.deregister_service()