from .consul_utils import (
    ConsulClient, 
    CONSUL_CLIENT,
)
from typing import (
    List,
    LiteralString,
)

__all__: List[LiteralString] = [
    "ConsulClient",
    "CONSUL_CLIENT",
]