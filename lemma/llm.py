import os,json
from openai import OpenAI

MODELS={
    "strong":"grok-4-fast-reasoning",
    "fast":"grok-4-fast-reasoning",
    "vision":"grok-2-vision-1212",
    "cheap":"grok-4-fast-reasoning",
}
_DEFAULTS=dict(MODELS)
COST_PER_M={"grok-4-fast-reasoning":(0.20,0.50),
            "grok-4-fast-non-reasoning":(0.20,0.50),
            "grok-3":(3.00,15.00),"grok-3-mini":(0.30,0.50),
            "grok-2-vision-1212":(2.00,10.00)}

class LLM:
    def __init__(self,key=None,base="https://api.x.ai/v1"):
        self.c=OpenAI(api_key=key or os.getenv("XAI_API_KEY"),base_url=base)
        self.tok_in=0;self.tok_out=0;self.calls=0
        self.errors=0;self.parses_ok=0;self.parses_fail=0
        self._model_tok={}
    def chat(self,msgs,role="fast",json_mode=False,temp=0.7,
             frequency_penalty=None,presence_penalty=None,**kw):
        model=MODELS.get(role,role)
        p={"model":model,"messages":msgs,"temperature":temp}
        if json_mode:p["response_format"]={"type":"json_object"}
        if frequency_penalty is not None and "reasoning" not in model:
            p["frequency_penalty"]=frequency_penalty
        if presence_penalty is not None and "reasoning" not in model:
            p["presence_penalty"]=presence_penalty
        p.update(kw)
        r=self.c.chat.completions.create(**p)
        self.calls+=1
        if r.usage:
            self.tok_in+=r.usage.prompt_tokens
            self.tok_out+=r.usage.completion_tokens
            mt=self._model_tok.setdefault(model,{"in":0,"out":0})
            mt["in"]+=r.usage.prompt_tokens;mt["out"]+=r.usage.completion_tokens
        return r.choices[0].message.content
    def ask(self,prompt,sys="You are a research assistant.",role="fast",**kw):
        return self.chat([{"role":"system","content":sys},
                          {"role":"user","content":prompt}],role=role,**kw)
    def structured(self,prompt,schema,role="fast",**kw):
        sys=f"Respond in valid JSON only. No extra text. Target schema:\n{json.dumps(schema)}"
        r=self.chat([{"role":"system","content":sys},
                      {"role":"user","content":prompt}],role=role,json_mode=True,**kw)
        try:
            d=json.loads(r);self.parses_ok+=1;return d
        except json.JSONDecodeError:
            for start in [r.find('{'),r.find('[')]:
                if start<0:continue
                depth=0;end=start
                opener=r[start]
                closer='}' if opener=='{' else ']'
                for i in range(start,min(len(r),start+50000)):
                    if r[i]==opener:depth+=1
                    elif r[i]==closer:depth-=1
                    if depth==0:end=i+1;break
                try:
                    d=json.loads(r[start:end]);self.parses_ok+=1;return d
                except:continue
            self.parses_fail+=1
            return {}
    def vision(self,prompt,image_urls,role="vision"):
        content=[{"type":"text","text":prompt}]
        for u in image_urls:
            content.append({"type":"image_url","image_url":{"url":u}})
        return self.chat([{"role":"user","content":content}],role=role)
    def usage(self):
        cost=0.0
        for model,toks in self._model_tok.items():
            rates=COST_PER_M.get(model,(0.20,0.50))
            cost+=toks["in"]*rates[0]/1e6+toks["out"]*rates[1]/1e6
        return {"calls":self.calls,"tok_in":self.tok_in,"tok_out":self.tok_out,
                "cost_usd":round(cost,4),"by_model":dict(self._model_tok),
                "parses_ok":self.parses_ok,"parses_fail":self.parses_fail,
                "errors":self.errors}
    @staticmethod
    def reset_models():
        for k,v in _DEFAULTS.items():MODELS[k]=v
    @staticmethod
    def override_all(model):
        for k in MODELS:MODELS[k]=model
