from typing import Protocol, Any 
from pathlib import Path 

class ProtoProtocol(Protocol): 
    
    def extract(self, **kwargs: dict[Any, Any])->None: 
        ...

    def save(self, path: Path|str, **kwargs: dict[Any, Any])->None: 
        ... 