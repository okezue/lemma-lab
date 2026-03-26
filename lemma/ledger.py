import json,os
from .models import Obs

class Ledger:
    def __init__(self,path=None):
        self.obs={};self.path=path
        if path and os.path.exists(path):self.load()
    def add(self,o):
        if isinstance(o,dict):o=Obs.from_dict(o)
        self.obs[o.id]=o;return o
    def get(self,id):return self.obs.get(id)
    def query(self,src=None,mod=None,t0=None,t1=None,kw=None):
        r=list(self.obs.values())
        if src:r=[o for o in r if o.src==src]
        if mod:r=[o for o in r if o.mod==mod]
        if t0:r=[o for o in r if o.ts>=t0]
        if t1:r=[o for o in r if o.ts<=t1]
        if kw:r=[o for o in r if kw.lower() in o.content.lower()]
        return sorted(r,key=lambda o:o.ts)
    def save(self):
        if not self.path:return
        with open(self.path,'w') as f:
            json.dump({k:v.to_dict() for k,v in self.obs.items()},f)
    def load(self):
        with open(self.path) as f:
            d=json.load(f)
            self.obs={k:Obs.from_dict(v) for k,v in d.items()}
    def __len__(self):return len(self.obs)
    def summary(self):return f"Ledger: {len(self)} observations"
