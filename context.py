from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class UniversalDummy:
    def __call__(self, *args, **kwargs): return self
    def __getattr__(self, item): return self
    
    def __await__(self):
        async def _dummy(): return None
        return _dummy().__await__()
    
    def __bool__(self): return False
    def __str__(self): return ""
    
    def __iter__(self):
        return iter([])

class SafeBaseModel(BaseModel):
    def __getattr__(self, item):
        return UniversalDummy()
    
    class Config:
        arbitrary_types_allowed = True
        extra = "allow"


class FakeRunConfig(SafeBaseModel):
    response_modalities: List[str] = ["TEXT"]
class FakePluginManager:
    def __getattr__(self, item):
        return UniversalDummy()

class FakeSession(SafeBaseModel):
    id: str = "local-test-session"
    state: dict = Field(default_factory=dict)
    events: List[Any] = Field(default_factory=list)

class FakeContext(SafeBaseModel):
    session: FakeSession = Field(default_factory=FakeSession)
    
    input: Any = None  
    agent: Any = None 
    
    invocation_id: str = "local-test-invocation-001"
    branch: str = "default"
    flow_name: str = "default_flow"

    plugin_manager: Any = Field(default_factory=FakePluginManager)
    run_config: FakeRunConfig = Field(default_factory=FakeRunConfig)
    agent_states: Dict[str, Any] = Field(default_factory=dict)
    end_invocation: bool = False

    def _get_events(self, **kwargs):
        return []