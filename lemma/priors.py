import json,os
from .models import Prior,APrior

class PriorLib:
    def __init__(self,path=None):
        self.priors={};self.anti={};self.path=path
        if path and os.path.exists(path):self.load()
    def add(self,p):
        if isinstance(p,dict):p=Prior.from_dict(p)
        self.priors[p.id]=p;return p
    def add_anti(self,ap):
        if isinstance(ap,dict):ap=APrior.from_dict(ap)
        self.anti[ap.id]=ap;return ap
    def get(self,id):return self.priors.get(id)
    def active(self):return [p for p in self.priors.values() if p.active]
    def match(self,query,top=5):
        q=query.lower()
        scored=[]
        for p in self.active():
            s=sum(1 for w in q.split() if w in p.stmt.lower() or w in p.scope.lower())
            if s>0:scored.append((s*p.xfer,p))
        scored.sort(key=lambda x:-x[0])
        return [p for _,p in scored[:top]]
    def promote(self,stmt,typ="domain",scope="",evidence=None,assumptions=None):
        p=Prior(stmt=stmt,type=typ,scope=scope,
                evidence=evidence or [],assumptions=assumptions or [])
        return self.add(p)
    def demote(self,id):
        p=self.get(id)
        if p:p.active=False;return True
        return False
    def dependents_of(self,id):
        return [p for p in self.active() if id in p.evidence]
    def to_context(self):
        ps=self.active()
        lines=[f"[{p.id}] ({p.type}) {p.stmt}" for p in ps]
        if self.anti:
            lines.append("\nAnti-priors:")
            for ap in self.anti.values():
                lines.append(f"[{ap.id}] {ap.stmt}")
        return "\n".join(lines) if lines else "(no priors)"
    def save(self):
        if not self.path:return
        with open(self.path,'w') as f:
            json.dump({"priors":{k:v.to_dict() for k,v in self.priors.items()},
                       "anti":{k:v.to_dict() for k,v in self.anti.items()}},f)
    def load(self):
        with open(self.path) as f:
            d=json.load(f)
            self.priors={k:Prior.from_dict(v) for k,v in d.get("priors",{}).items()}
            self.anti={k:APrior.from_dict(v) for k,v in d.get("anti",{}).items()}
    def __len__(self):return len(self.priors)
