class ToolRegistry:
    def __init__(self):
        self._tools={};self._traces=[]
    def register(self,name,fn,desc=""):
        self._tools[name]={"fn":fn,"desc":desc}
    def call(self,name,**kw):
        t=self._tools.get(name)
        if not t:return {"error":f"Unknown tool: {name}"}
        r=t["fn"](**kw)
        self._traces.append({"tool":name,"args":{k:str(v)[:100] for k,v in kw.items()},
                             "result_preview":str(r)[:200]})
        return r
    def list_tools(self):
        return [f"{k}: {v['desc']}" for k,v in self._tools.items()]
    def get_traces(self,n=20):
        return self._traces[-n:]
    def has(self,name):return name in self._tools
    def add_composite(self,name,desc,steps):
        def composite(**kw):
            results=[]
            for s in steps:
                tn=s.get("tool","")
                args=s.get("args",{})
                args.update(kw)
                if self.has(tn):results.append(self.call(tn,**args))
            return results
        self.register(name,composite,desc)
