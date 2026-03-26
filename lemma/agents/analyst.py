import json
from .base import BaseAgent
from ..models import Obs,Claim

class AnalystAgent(BaseAgent):
    def run(self,focus="full"):
        data=self._gather_data()
        analysis=self._run_analysis(data,focus)
        graphs=self._generate_graphs(data,analysis)
        checks=self._check_claims_against_data(data)
        return {"analysis":analysis,"graphs":graphs,"checks":checks}
    def _gather_data(self):
        d={"posts_by_day":{},"posts_by_src":{},"posts_by_lang":{},"posts_by_type":{},
           "bot_posts":[],"verified_posts":[],"figures":[],"papers":[],
           "total":len(self.ledger),"claim_count":len(self.graph)}
        for o in self.ledger.obs.values():
            day=o.meta.get("day","?")
            d["posts_by_day"][day]=d["posts_by_day"].get(day,0)+1
            d["posts_by_src"][o.src]=d["posts_by_src"].get(o.src,0)+1
            lang=o.meta.get("lang","?")
            d["posts_by_lang"][lang]=d["posts_by_lang"].get(lang,0)+1
            typ=o.meta.get("type","?")
            d["posts_by_type"][typ]=d["posts_by_type"].get(typ,0)+1
            if o.meta.get("is_bot") or o.meta.get("persona")=="bot_amplifier":
                d["bot_posts"].append({"src":o.src,"day":day,"lang":lang})
            badge=o.meta.get("account",{}).get("badge","none")
            if badge in ("blue_check","org_gold"):
                d["verified_posts"].append({"src":o.src,"day":day})
            if o.mod=="figure_desc":d["figures"].append(o.to_dict())
            if o.mod in ("paper_abstract","paper_appendix","errata","replication_report"):
                d["papers"].append({"type":o.mod,"content":o.content[:200]})
        return d
    def _run_analysis(self,data,focus):
        sys=self._sys(
            "You are a data analyst. Analyze this dataset and produce insights. "
            "Generate statistical summaries, detect patterns, identify anomalies. "
            "Be quantitative and specific.")
        prompt=(
            f"Dataset analysis (focus: {focus}):\n\n"
            f"Total observations: {data['total']}\n"
            f"Claims in graph: {data['claim_count']}\n"
            f"Posts by day: {json.dumps(dict(sorted(data['posts_by_day'].items())))}\n"
            f"Posts by language (top 15): {json.dumps(dict(sorted(data['posts_by_lang'].items(),key=lambda x:-x[1])[:15]))}\n"
            f"Posts by type: {json.dumps(data['posts_by_type'])}\n"
            f"Bot posts: {len(data['bot_posts'])}\n"
            f"Verified posts: {len(data['verified_posts'])}\n"
            f"Top sources: {json.dumps(dict(sorted(data['posts_by_src'].items(),key=lambda x:-x[1])[:10]))}\n"
            f"Papers: {len(data['papers'])}\n"
            f"Figures: {len(data['figures'])}\n\n"
            f"Current claims:\n{self._claims_ctx(15)}\n\n"
            f"Produce analysis. Return JSON:\n"
            f'{{"summary":"overall narrative of what the data shows",'
            f'"patterns":["pattern 1","pattern 2"],'
            f'"anomalies":["anomaly 1"],'
            f'"bot_analysis":{{"ratio":0.3,"pattern":"description"}},'
            f'"language_dynamics":"how languages interact",'
            f'"temporal_pattern":"how discourse evolved over time",'
            f'"credibility_distribution":"who is credible vs not",'
            f'"key_metrics":{{"metric1":0.5}}}}')
        return self.llm.structured(f"{sys}\n\n{prompt}",{"type":"object"},role="strong")
    def _generate_graphs(self,data,analysis):
        sys="You are a data visualization designer. Propose graph specifications for key findings."
        prompt=(
            f"Analysis results:\n{json.dumps(analysis,indent=1,default=str)[:1000]}\n\n"
            f"Data available:\n"
            f"- posts_by_day: {json.dumps(dict(sorted(data['posts_by_day'].items())))}\n"
            f"- posts_by_lang: {json.dumps(dict(sorted(data['posts_by_lang'].items(),key=lambda x:-x[1])[:10]))}\n"
            f"- posts_by_type: {json.dumps(data['posts_by_type'])}\n"
            f"- bot_count: {len(data['bot_posts'])}\n\n"
            f"Propose 3-5 graph specifications. Return JSON:\n"
            f'{{"graphs":[{{"title":"Graph Title",'
            f'"type":"bar|line|pie|scatter|heatmap|network",'
            f'"x_axis":"label","y_axis":"label",'
            f'"data_points":{{"key":value}},'
            f'"insight":"what this graph reveals",'
            f'"matplotlib_code":"python code to generate this plot"}}]}}')
        return self.llm.structured(f"{sys}\n\n{prompt}",{"type":"object"},role="fast")
    def _check_claims_against_data(self,data):
        claims=self.graph.all_claims()
        if not claims:return {"checks":[],"summary":"no claims to check"}
        claims_text="\n".join(f"[{c.id}] (conf={c.conf:.2f}) {c.stmt}" for c in claims[:15])
        sys=self._sys("You are a fact-checker. Verify claims against actual data.")
        prompt=(
            f"Claims to verify:\n{claims_text}\n\n"
            f"Actual data:\n"
            f"- Bot ratio: {len(data['bot_posts'])}/{data['total']} = {len(data['bot_posts'])/max(data['total'],1):.1%}\n"
            f"- Languages: {len(data['posts_by_lang'])}\n"
            f"- Papers found: {len(data['papers'])}\n"
            f"- Figures found: {len(data['figures'])}\n"
            f"- Paper excerpts: {json.dumps([p['content'][:100] for p in data['papers'][:3]])}\n\n"
            f"Check each claim. Return JSON:\n"
            f'{{"checks":[{{"claim_id":"...","claim":"...",'
            f'"verdict":"confirmed|partially_confirmed|unconfirmed|contradicted",'
            f'"evidence":"what data supports/contradicts this",'
            f'"revised_confidence":0.7}}],'
            f'"summary":"overall assessment"}}')
        r=self.llm.structured(f"{sys}\n\n{prompt}",{"type":"object"},role="strong")
        for check in r.get("checks",[]):
            cid=check.get("claim_id","")
            c=self.graph.get(cid)
            if c and "revised_confidence" in check:
                old=c.conf
                c.conf=check["revised_confidence"]
                if check.get("verdict")=="contradicted":c.status="contradicted"
                elif check.get("verdict")=="confirmed" and c.conf>0.7:c.status="supported"
        return r
