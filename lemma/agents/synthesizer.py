import json
from .base import BaseAgent

class SynthAgent(BaseAgent):
    def run(self,conjecture,hyps,branches):
        evidence_summary=self._gather_evidence()
        narrative_vs_evidence=self._check_narrative_split()
        sys=self._sys(
            "You are a research synthesizer. Produce a final report that "
            "SEPARATES object-level truth from narrative-level belief. "
            "Ground all conclusions in actual evidence from the dataset.")
        claims=self._claims_ctx(30)
        hs="\n".join(f"- [{h.id}] {h.stmt} (status={h.status}, conf={h.conf})"
                     for h in hyps)
        bs="\n".join(f"- [{b.id}] hyp={b.hyp_id} sup={len(b.sup)} "
                     f"con={len(b.con)} conf={b.conf}" for b in branches)
        prompt=(
            f"Original conjecture: {conjecture}\n\n"
            f"Hypotheses tested:\n{hs}\n\n"
            f"Branches:\n{bs}\n\n"
            f"Claim graph (top claims):\n{claims}\n\n"
            f"Evidence summary:\n{evidence_summary}\n\n"
            f"Narrative vs Evidence analysis:\n{narrative_vs_evidence}\n\n"
            f"Produce synthesis report as JSON:\n"
            f'{{"object_conclusion":"what is likely TRUE based on evidence",'
            f'"narrative_conclusion":"what people BELIEVED and why",'
            f'"divergence":"why truth and narrative diverged",'
            f'"top_support":["strongest supporting evidence with sources"],'
            f'"top_counter":["strongest counter-evidence with sources"],'
            f'"unresolved":["questions still open"],'
            f'"new_priors":["reusable insights learned"],'
            f'"confidence":0.7}}')
        return self.llm.structured(f"{sys}\n\n{prompt}",{"type":"object"},role="strong")

    def _gather_evidence(self):
        parts=[]
        if self.tools:
            for mod in ["paper_abstract","paper_appendix","errata",
                        "replication_report","figure_desc"]:
                r=self.tools.call("search_by_modality",mod=mod)
                if isinstance(r,list) and r:
                    parts.append(f"\n{mod} ({len(r)} items):")
                    for item in r[:3]:
                        c=item.get("content","")[:150]
                        parts.append(f"  - {c}")
        return "\n".join(parts) if parts else "(no evidence tools available)"

    def _check_narrative_split(self):
        if not self.tools:return "(no tools)"
        social=self.tools.call("search_by_modality",mod="x_post")
        papers=self.tools.call("search_by_modality",mod="paper_abstract")
        n_social=len(social) if isinstance(social,list) else 0
        n_papers=len(papers) if isinstance(papers,list) else 0
        bot_posts=[]
        if isinstance(social,list):
            bot_posts=[p for p in social
                       if p.get("meta",{}).get("is_bot") or
                       p.get("meta",{}).get("persona")=="bot_amplifier"]
        return (f"Social posts: {n_social}, Paper/evidence items: {n_papers}, "
                f"Bot posts: {len(bot_posts)}, "
                f"Bot ratio: {len(bot_posts)/max(n_social,1):.1%}")
