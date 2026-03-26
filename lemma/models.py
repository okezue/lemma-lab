from dataclasses import dataclass,field,asdict
from enum import Enum
import uuid,time,json

def uid(p=""):return f"{p}{uuid.uuid4().hex[:8]}"

class CS(Enum):
    ACT="active";SUP="supported";CON="contradicted";STL="stale"
class HS(Enum):
    OPEN="open";PRV="proving";OK="proved";BRK="broken";STL="stale"
class PT(Enum):
    DOM="domain";SRC="source";PROC="procedural"
class Rel(Enum):
    SUP="support";CON="contradict";DEP="depend"

@dataclass
class Obs:
    id:str=field(default_factory=lambda:uid("O"))
    src:str=""
    content:str=""
    mod:str="text"
    ts:float=field(default_factory=time.time)
    meta:dict=field(default_factory=dict)
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d):return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class Claim:
    id:str=field(default_factory=lambda:uid("C"))
    stmt:str=""
    status:str="active"
    sup:list=field(default_factory=list)
    con:list=field(default_factory=list)
    deps:list=field(default_factory=list)
    src_obs:list=field(default_factory=list)
    conf:float=0.5
    ts:float=field(default_factory=time.time)
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d):return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class Hyp:
    id:str=field(default_factory=lambda:uid("H"))
    stmt:str=""
    why:str=""
    preds:list=field(default_factory=list)
    falsifiers:list=field(default_factory=list)
    tools:list=field(default_factory=list)
    prior_deps:list=field(default_factory=list)
    status:str="open"
    conf:float=0.5
    sup:list=field(default_factory=list)
    con:list=field(default_factory=list)
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d):return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class BCap:
    id:str=field(default_factory=lambda:uid("B"))
    hyp_id:str=""
    sup:list=field(default_factory=list)
    con:list=field(default_factory=list)
    assumptions:list=field(default_factory=list)
    pending:list=field(default_factory=list)
    next_act:str=""
    conf:float=0.5
    branch_deps:list=field(default_factory=list)
    depends_on_priors:list=field(default_factory=list)
    temporal_beliefs:list=field(default_factory=list)
    prov:list=field(default_factory=list)
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d):return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class Prior:
    id:str=field(default_factory=lambda:uid("P"))
    type:str="domain"
    stmt:str=""
    scope:str=""
    assumptions:list=field(default_factory=list)
    evidence:list=field(default_factory=list)
    cex:list=field(default_factory=list)
    xfer:float=0.5
    failures:list=field(default_factory=list)
    active:bool=True
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d):return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class APrior:
    id:str=field(default_factory=lambda:uid("AP"))
    stmt:str=""
    why:str=""
    trap:str=""
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d):return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class TRecipe:
    id:str=field(default_factory=lambda:uid("T"))
    name:str=""
    desc:str=""
    steps:list=field(default_factory=list)
    src_trace:str=""
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d):return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class ANote:
    id:str=field(default_factory=lambda:uid("AN"))
    target:str=""
    verdict:str=""
    issues:list=field(default_factory=list)
    ts:float=field(default_factory=time.time)
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d):return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})

@dataclass
class ACap:
    active:list=field(default_factory=list)
    stalled:list=field(default_factory=list)
    tensions:list=field(default_factory=list)
    next_exp:list=field(default_factory=list)
    ideas:list=field(default_factory=list)
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,d):return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})
