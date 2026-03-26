import json,os
from collections import defaultdict
from .models import Claim

class ClaimGraph:
    def __init__(self,path=None):
        self.claims={};self.edges=[];self.path=path
        if path and os.path.exists(path):self.load()
    def add(self,c):
        if isinstance(c,dict):c=Claim.from_dict(c)
        self.claims[c.id]=c;return c
    def get(self,id):return self.claims.get(id)
    def link(self,src,tgt,rel="support"):
        self.edges.append({"src":src,"tgt":tgt,"rel":rel})
        c=self.get(tgt)
        if not c:return
        if rel=="support":c.sup.append(src)
        elif rel=="contradict":c.con.append(src)
        elif rel=="depend":c.deps.append(src)
    def supporters(self,id):
        c=self.get(id)
        return [self.get(s) for s in (c.sup if c else []) if self.get(s)]
    def contradictors(self,id):
        c=self.get(id)
        return [self.get(s) for s in (c.con if c else []) if self.get(s)]
    def dependents(self,id):
        return [c for c in self.claims.values() if id in c.deps]
    def update_conf(self):
        for c in self.claims.values():
            ns,nc=len(c.sup),len(c.con)
            if ns+nc>0:c.conf=ns/(ns+nc)
            if nc>ns:c.status="contradicted"
            elif ns>nc and ns>=2:c.status="supported"
    def stale_from(self,prior_id):
        deps=self.dependents(prior_id)
        for d in deps:d.status="stale"
        return deps
    def summary(self):
        by_s=defaultdict(int)
        for c in self.claims.values():by_s[c.status]+=1
        return dict(by_s)
    def all_claims(self):return list(self.claims.values())
    def to_context(self,max_n=20):
        top=sorted(self.claims.values(),key=lambda c:c.conf,reverse=True)[:max_n]
        return "\n".join(f"[{c.id}] ({c.status},{c.conf:.2f}) {c.stmt}" for c in top)
    def save(self):
        if not self.path:return
        with open(self.path,'w') as f:
            json.dump({"claims":{k:v.to_dict() for k,v in self.claims.items()},
                       "edges":self.edges},f)
    def load(self):
        with open(self.path) as f:
            d=json.load(f)
            self.claims={k:Claim.from_dict(v) for k,v in d["claims"].items()}
            self.edges=d["edges"]
    def __len__(self):return len(self.claims)
