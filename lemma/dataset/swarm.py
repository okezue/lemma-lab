import json,random,time,hashlib,re,os,urllib.request,math

def _uid():return hashlib.md5(str(time.time()+random.random()).encode()).hexdigest()[:8]

MODELS=["grok-4-fast-non-reasoning","grok-3","grok-3-mini"]
MW=[0.6,0.25,0.15]

def _random_words(n=3):
    try:
        r=urllib.request.urlopen(f"https://random-word-api.herokuapp.com/word?number={n}",timeout=4)
        return json.loads(r.read())
    except:
        bank=["ocean","revolution","grandmother","telescope","monsoon","cinnamon",
              "cathedral","firefly","glacier","labyrinth","bamboo","thunder",
              "origami","volcano","saffron","midnight","accordion","avalanche",
              "chameleon","dandelion","eclipse","fossil","horizon","jasmine",
              "kaleidoscope","lantern","mosaic","nebula","oracle","pilgrim",
              "quartz","raven","silhouette","tapestry","umbrella","vortex",
              "wanderlust","zenith","archipelago","bohemian","chrysalis",
              "dervish","ephemeral","fjord","gossamer","halcyon","iridescent",
              "juxtapose","kinetic","luminous","melancholy","nomadic","obsidian",
              "paradox","quintessence","rhapsody","serendipity","transient",
              "utopia","vivacious","whimsical","canopy","ember","prism"]
        return random.sample(bank,min(n,len(bank)))

class Mem:
    def __init__(self):
        self.posts=[]
        self.seen=[]
        self.seen_profiles=[]
        self.notifs=[]
        self.dreams=[]
        self.life=[]
        self.persona_prompt=None
        self.reply_ct={}
        self.profile_edits=[]
        self.following=set()
        self.followers=set()
        self.interests_learned=[]
        self.web_topics=[]
    def replied_to(self,oid):self.reply_ct[oid]=self.reply_ct.get(oid,0)+1
    def stop_replying(self,oid,mx=3):return self.reply_ct.get(oid,0)>=mx
    def recall(self,n=6):
        return {"posts":self.posts[-n:],"notifs":self.notifs[-4:],
                "dreams":self.dreams[-3:],"life":self.life[-3:],
                "web":self.web_topics[-3:]}
    def compact(self,mx=20):
        for attr in ["posts","seen","notifs","dreams","life","seen_profiles","web_topics"]:
            lst=getattr(self,attr)
            if len(lst)>mx:setattr(self,attr,lst[-mx:])

class Agent:
    def __init__(self,persona=None,model=None):
        self.id=persona.get("id",f"a_{_uid()}") if persona else f"a_{_uid()}"
        self.persona=persona or {}
        self.mem=Mem()
        self.model=model or random.choices(MODELS,MW)[0]
        self.turn_count=0
        self.history_built=False
        self.energy=1.0
    def langs(self):return set(self.persona.get("langs",[self.persona.get("lang","en")]))
    def interests(self):return set(self.persona.get("interests",[]))
    def sys_prompt(self):
        if self.mem.persona_prompt:return self.mem.persona_prompt
        p=self.persona
        if not p:return "You are a user on X. Post naturally."
        extras=[]
        if self.mem.dreams:extras.append("Inner life:\n"+"\n".join(f"- {d}" for d in self.mem.dreams[-3:]))
        if self.mem.life:extras.append("Recent events:\n"+"\n".join(f"- {e}" for e in self.mem.life[-3:]))
        if self.mem.web_topics:extras.append("Topics you've been reading about:\n"+"\n".join(f"- {t}" for t in self.mem.web_topics[-3:]))
        ex="\n".join(extras)
        return (f"You are {p.get('name',self.id)} (@{self.id}) on X.\n"
                f"Bio: {p.get('bio','')}\n"
                f"Role: {p.get('role','')} | Style: {p.get('style','')}\n"
                f"Languages: {p.get('langs',['en'])} | Country: {p.get('country','')}\n"
                f"Interests: {p.get('interests',[])}\n"
                f"{ex}\n"
                f"Post in character. Mix languages naturally. Max 280 chars. "
                f"You can include links (real URLs from news, papers, tools you know).")
    def edit_profile(self,field,value):
        old=self.persona.get(field,"")
        self.persona[field]=value
        ts=time.strftime("%B %Y")
        self.mem.profile_edits.append({"field":field,"old":str(old)[:50],"new":str(value)[:50],"date":ts})
        if field=="id":
            self.persona.setdefault("username_changes",[]).append({"from":f"@{old}","date":ts})
            self.persona.setdefault("prev_usernames",[]).append(f"@{old}")

class Feed:
    def __init__(self):
        self.posts=[]
        self.idx={}
        self.by_lang={}
        self.by_src={}
    def add(self,post):
        self.posts.append(post);self.idx[post["id"]]=post
        lang=post.get("meta",{}).get("lang","en")
        self.by_lang.setdefault(lang,[]).append(post)
        self.by_src.setdefault(post["src"],[]).append(post)
    def get(self,id):return self.idx.get(id)
    def recent(self,n=30):return self.posts[-n:]
    def author(self,aid,n=10):return (self.by_src.get(aid,[]))[-n:]
    def lang_posts(self,lang,n=20):return (self.by_lang.get(lang,[]))[-n:]
    def trending(self,n=5):
        if len(self.posts)<5:return []
        words={}
        for p in self.posts[-150:]:
            for w in re.findall(r'#\w+',p.get("content","")):
                words[w]=words.get(w,0)+1
        return sorted(words.items(),key=lambda x:-x[1])[:n]
    def __len__(self):return len(self.posts)

def _score_post(post,agent):
    s=0.0
    plang=post.get("meta",{}).get("lang","en")
    alangs=agent.langs()
    if plang in alangs:s+=5.0
    if post["src"] in agent.mem.following:s+=4.0
    pinterests=set(re.findall(r'#(\w+)',post.get("content","").lower()))
    ainterests={i.lower() for i in agent.interests()}
    overlap=pinterests&ainterests
    if overlap:s+=2.0*len(overlap)
    acountry=agent.persona.get("country","")
    pcountry=post.get("meta",{}).get("account",{}).get("country","")
    if acountry and pcountry and acountry==pcountry:s+=1.5
    pb=post.get("meta",{}).get("account",{})
    if pb.get("badge") in ("blue_check","org_gold"):s+=1.0
    if pb.get("followers",0)>50000:s+=0.5
    s+=random.uniform(0,2.0)
    age=len(agent.mem.seen)
    s-=age*0.01
    return s

def _engage_prob(agent,post):
    p=0.15
    plang=post.get("meta",{}).get("lang","en")
    if plang in agent.langs():p+=0.25
    if post["src"] in agent.mem.following:p+=0.15
    if any(f"@{agent.id}" in post.get("content","")):p+=0.4
    if agent.energy<0.3:p*=0.3
    p=min(p,0.85)
    return p

class Swarm:
    def __init__(self,api_key,budget=5.0,out_dir="./dataset_data"):
        from ..llm import LLM
        self.llm=LLM(key=api_key)
        self.feed=Feed()
        self.agents={}
        self.budget=budget
        self.out_dir=out_dir
        os.makedirs(out_dir,exist_ok=True)
        self.tick_n=0
        self.log=[]

    def _cost(self):return self.llm.usage()["cost_usd"]
    def _over(self):return self._cost()>=self.budget
    def _call(self,msgs,agent,json_mode=False):
        try:
            p={"role":agent.model,"json_mode":json_mode,"temp":random.uniform(0.5,1.2)}
            if "non-reasoning" in agent.model or agent.model=="grok-3":
                try:return self.llm.chat(msgs,frequency_penalty=random.uniform(0.0,0.8),
                                         presence_penalty=random.uniform(0.0,0.8),**p)
                except:return self.llm.chat(msgs,**p)
            return self.llm.chat(msgs,**p)
        except:self.llm.errors+=1;return None

    def spawn(self):
        seed=_random_words(3)
        prev=[a.persona.get("country","") for a in self.agents.values()]
        avoid=""
        if prev:
            from collections import Counter
            avoid=f"\nAvoid: {[c for c,_ in Counter(prev).most_common(3)]}"
        prompt=(
            f"Create a new X user. Seeds: {seed}\n"
            f"Let these words shape who they are. ANY country, language, walk of life.\n"
            f"{avoid}\n\n"
            f'Return JSON: {{"id":"handle","name":"Name","bio":"bio (max 160)",'
            f'"role":"role","style":"post style","country":"country",'
            f'"lang":"primary code","langs":["codes"],'
            f'"followers":N,"following":N,"posts_count":N,'
            f'"joined":"Month YYYY","connected_via":"iOS App Store|Android Google Play|Web App",'
            f'"verified":false,"org_verified":false,"legacy_verified":false,'
            f'"account_type":"personal","header_desc":"header","pfp_desc":"pfp",'
            f'"interests":["t1","t2","t3"],"website":"","seed_words":{json.dumps(seed)}}}')
        a=Agent(model=random.choices(MODELS,MW)[0])
        r=self._call([{"role":"system","content":"Create a unique persona. Maximum diversity."},
                      {"role":"user","content":prompt}],a,json_mode=True)
        if not r:return None
        try:
            d=json.loads(r)
            d["id"]=re.sub(r'[^a-z0-9_]','',d.get("id",f"u_{_uid()}").lower())[:20] or f"u_{_uid()}"
            while d["id"] in self.agents:d["id"]=f"{d['id']}_{_uid()[:3]}"
            d.setdefault("username_changes",[]);d.setdefault("prev_usernames",[])
            a.id=d["id"];a.persona=d;self.agents[a.id]=a
            self._log(f"SPAWN @{a.id} ({d.get('name','?')}, {d.get('country','?')}, {d.get('langs',[])})")
            return a
        except:self.llm.parses_fail+=1;return None

    def dream(self,agent):
        if self._over():return
        seed=_random_words(2)
        p=agent.persona
        prompt=(f"You are {p.get('name',agent.id)} from {p.get('country','')}.\n"
                f"Role: {p.get('role','')}, interests: {p.get('interests',[])}\n"
                f"Seeds: {seed}\n\n"
                f"Generate 3-5 inner reflections/memories/life scenarios.\n"
                f"Be culturally specific to your daily reality.\n\n"
                f'Return JSON: {{"dreams":["..."],"life_events":["..."]}}')
        r=self._call([{"role":"system","content":"Generate inner life. Culturally specific."},
                      {"role":"user","content":prompt}],agent,json_mode=True)
        if not r:return
        try:
            d=json.loads(r)
            agent.mem.dreams.extend(d.get("dreams",[]));agent.mem.life.extend(d.get("life_events",[]))
            self._log(f"  DREAM @{agent.id}: +{len(d.get('dreams',[]))}d +{len(d.get('life_events',[]))}e")
        except:self.llm.parses_fail+=1

    def build_history(self,agent):
        if self._over() or agent.history_built:return
        agent.history_built=True
        p=agent.persona
        prompt=(
            f"Generate 5-8 historical posts by @{agent.id} ({p.get('name','')}).\n"
            f"Bio: {p.get('bio','')}, Role: {p.get('role','')}\n"
            f"Country: {p.get('country','')}, Langs: {p.get('langs',['en'])}\n"
            f"Style: {p.get('style','')}, Interests: {p.get('interests',[])}\n"
            f"Dreams: {agent.mem.dreams[:2]}\n\n"
            f"Realistic posts — mundane life, opinions, jokes, professional stuff.\n"
            f"In their language(s). Some can have media or links.\n\n"
            f'Return JSON: {{"posts":[{{"content":"text","lang":"code",'
            f'"media":[{{"type":"image|gif|link_preview|video","desc":"..."}}],'
            f'"days_ago":N}}]}}')
        r=self._call([{"role":"system","content":"Generate historical posts."},
                      {"role":"user","content":prompt}],agent,json_mode=True)
        if not r:return
        try:
            d=json.loads(r)
            for hp in d.get("posts",[]):
                post={"id":f"H{_uid()}","content":hp.get("content","")[:280],
                      "src":agent.id,"modality":"x_post",
                      "meta":{"day":-(hp.get("days_ago",1)),"type":"post",
                              "lang":hp.get("lang",p.get("lang","en")),
                              "media":hp.get("media",[]),"is_history":True,
                              "model":agent.model,"account":_badge(p)}}
                self.feed.add(post)
                agent.mem.posts.append({"id":post["id"],"content":post["content"][:80]})
            self._log(f"  HISTORY @{agent.id}: +{len(d.get('posts',[]))}")
        except:self.llm.parses_fail+=1

    def web_discover(self,agent):
        if self._over():return
        interests=agent.persona.get("interests",["technology"])
        topic=random.choice(interests)
        prompt=(f"You are @{agent.id}, interested in '{topic}'.\n"
                f"What's something interesting happening in '{topic}' right now "
                f"that you might want to post about? Give a specific real topic, "
                f"event, link, or trend. Be current and specific.\n\n"
                f'Return JSON: {{"topic":"specific topic","summary":"1 sentence",'
                f'"possible_link":"url or empty","hashtags":["#tag1"]}}')
        r=self._call([{"role":"system","content":"You surface real-world topics for social media users."},
                      {"role":"user","content":prompt}],agent,json_mode=True)
        if not r:return
        try:
            d=json.loads(r)
            agent.mem.web_topics.append(d)
            self._log(f"  WEB @{agent.id}: {d.get('topic','?')[:60]}")
        except:self.llm.parses_fail+=1

    def build_feed(self,agent):
        candidates=[]
        for lang in agent.langs():
            candidates.extend(self.feed.lang_posts(lang,15))
        candidates.extend(self.feed.recent(20))
        for fid in agent.mem.following:
            candidates.extend(self.feed.author(fid,5))
        for n in agent.mem.notifs[-3:]:
            p=self.feed.get(n.get("post_id",""))
            if p:candidates.append(p)
        seen=set();unique=[]
        for p in candidates:
            if p["id"] not in seen and p["src"]!=agent.id:
                seen.add(p["id"]);unique.append(p)
        scored=[(p,_score_post(p,agent)) for p in unique]
        scored.sort(key=lambda x:-x[1])
        lines=[]
        for p,sc in scored[:12]:
            pb=p.get("meta",{}).get("account",{})
            badge=" ✓" if pb.get("badge") in ("blue_check","org_gold") else ""
            typ=p.get("meta",{}).get("type","post")
            tag={"reply":" [reply]","quote":" [QT]","retweet":" [RT]"}.get(typ,"")
            media=""
            pm=p.get("meta",{}).get("media",[])
            if pm:media=f" [{pm[0].get('type','media')}]"
            lines.append(f"[{p['id']}] @{p['src']}{badge}: {p['content'][:120]}{tag}{media}")
            agent.mem.seen.append(p["id"])
        return "\n".join(lines) if lines else "(empty feed)"

    def scroll_profiles(self,agent):
        others=list(self.agents.values())
        random.shuffle(others)
        same_lang=[a for a in others if a.id!=agent.id and a.langs()&agent.langs()]
        diff=[a for a in others if a.id!=agent.id and a not in same_lang]
        targets=(same_lang[:2]+diff[:1])[:3]
        if not targets:return
        for t in targets:
            card=(f"@{t.id} | {t.persona.get('name','')} "
                  f"{'✓' if t.persona.get('verified') else ''}\n"
                  f"Bio: {t.persona.get('bio','')}\n"
                  f"{t.persona.get('country','')} | {t.persona.get('langs',[])}\n"
                  f"Followers: {t.persona.get('followers',0)}")
            agent.mem.seen_profiles.append({"id":t.id,"card":card[:200]})
            if t.id not in agent.mem.following and random.random()<0.3:
                agent.mem.following.add(t.id)
                t.mem.followers.add(agent.id)
                self._log(f"  @{agent.id} followed @{t.id}")
        self._log(f"  @{agent.id} browsed [{','.join(t.id for t in targets)}]")

    def maybe_edit_profile(self,agent):
        if self._over() or random.random()>0.12:return False
        p=agent.persona
        prompt=(f"You're @{agent.id}. Thinking about updating your profile.\n"
                f"Current: name={p.get('name','')}, bio={p.get('bio','')}\n"
                f"Recent life: {agent.mem.life[-2:] if agent.mem.life else 'nothing'}\n"
                f"Only change if there's a real reason.\n"
                f'Return JSON: {{"change":true,"field":"bio|header_desc|name","new_value":"...","reason":"..."}} or {{"change":false}}')
        r=self._call([{"role":"system","content":agent.sys_prompt()},
                      {"role":"user","content":prompt}],agent,json_mode=True)
        if not r:return False
        try:
            d=json.loads(r)
            if d.get("change") and d.get("field") in ("bio","header_desc","name","id"):
                agent.edit_profile(d["field"],d["new_value"])
                self._log(f"  PROFILE @{agent.id}: {d['field']} -> '{str(d['new_value'])[:40]}' ({d.get('reason','')})")
                return True
        except:self.llm.parses_fail+=1
        return False

    def agent_act(self,agent):
        if self._over():return
        agent.turn_count+=1;agent.mem.compact()
        agent.energy=max(0.1,agent.energy-0.08+random.uniform(-0.05,0.1))
        if agent.energy<0.2 and random.random()<0.6:
            self._log(f"  @{agent.id} low energy, resting");agent.energy+=0.3;return
        feed_view=self.build_feed(agent)
        mem=agent.mem.recall(5)
        fatigue=""
        heavy=[f"@{k}" for k,v in agent.mem.reply_ct.items() if v>=2]
        if heavy:fatigue=f"\nYou've replied a lot to {heavy}. Try someone new or post about YOUR life."
        profiles=""
        if agent.mem.seen_profiles:
            profiles="\nProfiles browsed:\n"+"\n".join(p["card"][:80] for p in agent.mem.seen_profiles[-2:])
        web=""
        if agent.mem.web_topics:
            wt=agent.mem.web_topics[-1]
            web=f"\nTopic you've been reading about: {wt.get('topic','')}"
            if wt.get("possible_link"):web+=f" ({wt['possible_link']})"
        following_ctx=f"\nFollowing: {list(agent.mem.following)[:8]}" if agent.mem.following else ""
        ctx=(f"Your posts: {json.dumps(mem['posts'][-3:],ensure_ascii=False)}\n"
             f"Notifications: {json.dumps(mem['notifs'],ensure_ascii=False)}\n"
             f"Your feed (personalized):\n{feed_view}\n"
             f"Trending: {self.feed.trending()}"
             f"{following_ctx}{profiles}{web}{fatigue}")
        prompt=(
            f"{ctx}\n\n"
            f"What do you do? You DON'T have to do anything. Options:\n"
            f"1. post — share a thought, opinion, life update, link, meme idea\n"
            f"2. reply — respond to someone [give post ID]\n"
            f"3. quote — quote-post with your take [give post ID]\n"
            f"4. retweet — share without comment [give post ID]\n"
            f"5. idle — just scroll, do nothing\n\n"
            f"Be natural. Most of the time people just scroll.\n"
            f"When you DO post, be yourself — your life, your language, your culture.\n"
            f"You can include links (news articles, tools, papers, videos).\n"
            f"You can describe media you'd attach (images, gifs, videos).\n"
            f"You can @mention anyone you want to talk to.\n\n"
            f'Return JSON: {{"action":"post|reply|quote|retweet|idle",'
            f'"content":"text (max 280, any lang, empty for RT/idle)",'
            f'"target_id":"post_id for reply/quote/RT or empty",'
            f'"lang":"code","media":[{{"type":"image|gif|video|link_preview","desc":"..."}}]}}')
        r=self._call([{"role":"system","content":agent.sys_prompt()},
                      {"role":"user","content":prompt}],agent,json_mode=True)
        if not r:return
        try:d=json.loads(r)
        except:self.llm.parses_fail+=1;return
        act=d.get("action","idle")
        if act=="idle":
            agent.energy+=0.15;return
        tid=d.get("target_id","")
        if act=="retweet":
            orig=self.feed.get(tid)
            if not orig:return
            post={"id":f"RT{_uid()}","content":f"RT @{orig['src']}: {orig['content'][:200]}",
                  "src":agent.id,"modality":"x_post",
                  "meta":{"day":self.tick_n,"type":"retweet","retweet_of":tid,
                          "lang":orig.get("meta",{}).get("lang","en"),
                          "media":[],"model":agent.model,"account":_badge(agent.persona)}}
            self.feed.add(post)
            agent.mem.posts.append({"id":post["id"],"content":f"RT @{orig['src']}"})
            self._log(f"  @{agent.id} [RT] @{orig['src']}: {orig['content'][:50]}")
            return
        content=d.get("content","")
        if not content:return
        if act=="reply" and tid:
            target=self.feed.get(tid)
            if target:
                if agent.mem.stop_replying(target["src"]):act="post";tid=""
                else:agent.mem.replied_to(target["src"])
        post={"id":f"SW{_uid()}","content":content[:280],"src":agent.id,
              "modality":"x_post",
              "meta":{"day":self.tick_n,"type":act,
                      "lang":d.get("lang",agent.persona.get("lang","en")),
                      "media":d.get("media",[]),
                      "reply_to":tid if act=="reply" else "",
                      "quote_of":tid if act=="quote" else "",
                      "model":agent.model,"turn":agent.turn_count,
                      "account":_badge(agent.persona)}}
        self.feed.add(post)
        agent.mem.posts.append({"id":post["id"],"content":content[:80]})
        self._log(f"  @{agent.id} [{act}] ({d.get('lang','?')}): {content[:80]}")
        for m in re.findall(r'@(\w+)',content):
            if m in self.agents and m!=agent.id:
                self.agents[m].mem.notifs.append(
                    {"from":agent.id,"post_id":post["id"],"preview":content[:80],"type":"mention"})
                self._log(f"    -> @{m}")

    def evolve_persona(self,agent):
        if self._over():return
        history=self.feed.author(agent.id,10)
        if len(history)<3:return
        posts_text="\n".join(f"- {p['content'][:150]}" for p in history)
        prompt=(f"Based on @{agent.id}'s posts, write a persona (3-4 sentences) "
                f"capturing their voice, interests, and style.\n\n"
                f"Posts:\n{posts_text}\n"
                f"Bio: {agent.persona.get('bio','')}, Country: {agent.persona.get('country','')}\n"
                f"Dreams: {agent.mem.dreams[-2:]}")
        obs=Agent(model="grok-4-fast-non-reasoning")
        r=self._call([{"role":"system","content":"Write persona descriptions from behavior."},
                      {"role":"user","content":prompt}],obs)
        if r:
            agent.mem.persona_prompt=r.strip()
            self._log(f"  EVOLVED @{agent.id}: {r[:80]}...")

    def inject_topic(self):
        topics=[
            "What's the most overhyped AI paper this month?",
            "Hot take: benchmarks are broken",
            "Just saw a model claiming multilingual support but it only tested on 5 languages...",
            "Why does nobody talk about low-resource languages in AI?",
            "My language isn't even in any benchmark. Are we invisible?",
            "I replicated a top paper and the results... don't match.",
            "What's everyone working on this weekend?",
            "Morning thoughts — what made you smile today?",
            "Share something beautiful from where you live",
            "What's a word in your language with no English translation?",
            "Late night thoughts thread ↓",
            "Unpopular opinion about your field — go",
            "What's a problem in your life that tech hasn't solved?",
            "Drop your favorite paper/article from this week",
            "The vibes on this app today are [fill in the blank]",
            "Anyone else doom-scrolling at 3am? What timezone are you in?",
        ]
        post={"id":f"TP{_uid()}","content":random.choice(topics),
              "src":"_topic_seed","modality":"x_post",
              "meta":{"day":self.tick_n,"type":"post","lang":"en","media":[]}}
        self.feed.add(post)

    def tick(self):
        if self._over():return False
        self.tick_n+=1
        if self.tick_n%4==0:self.inject_topic()
        spawn_n=0
        if self.tick_n%2==0 and not self._over():
            batch=random.randint(1,3)
            for _ in range(batch):
                if self._over():break
                a=self.spawn()
                if a:
                    spawn_n+=1
                    if not self._over():self.dream(a)
                    if not self._over():self.build_history(a)
        n=min(random.randint(3,8),len(self.agents))
        active=random.sample(list(self.agents.values()),n) if self.agents else []
        for a in active:
            if self._over():break
            roll=random.random()
            if roll<0.04:self.maybe_edit_profile(a)
            elif roll<0.09 and len(a.mem.dreams)<8:self.dream(a)
            elif roll<0.14:self.web_discover(a)
            elif roll<0.20:self.scroll_profiles(a)
            else:self.agent_act(a)
        if self.tick_n%8==0 and not self._over():
            cands=[a for a in self.agents.values()
                   if len(self.feed.author(a.id))>=3 and not a.mem.persona_prompt]
            if cands:self.evolve_persona(random.choice(cands))
        for a in self.agents.values():
            if a in active or self._over():continue
            pending=[n for n in a.mem.notifs[-3:] if not a.mem.stop_replying(n.get("from",""))]
            if not pending:continue
            notif=pending[-1]
            notif_post=self.feed.get(notif.get("post_id",""))
            if not notif_post:continue
            plang=notif_post.get("meta",{}).get("lang","en")
            prob=0.3
            if plang in a.langs():prob=0.6
            if f"@{a.id}" in notif_post.get("content",""):prob=0.75
            if random.random()<prob:
                self.agent_act(a)
                a.mem.notifs=[n for n in a.mem.notifs if n.get("post_id")!=notif.get("post_id")]
        return not self._over()

    def run(self,n_seed=10,max_ticks=500):
        print(f"{'='*60}")
        print(f"SWARM — ${self.budget:.2f} budget, {n_seed} seeds")
        print(f"{'='*60}")
        t0=time.time()
        print(f"\nPhase 1: Spawn + dream + history...")
        for _ in range(n_seed):
            if self._over():break
            a=self.spawn()
            if a and not self._over():
                self.dream(a)
                if not self._over():self.build_history(a)
        print(f"  {len(self.agents)} agents, {len(self.feed)} posts, ${self._cost():.4f}")
        print(f"\nPhase 2: Live...")
        for t in range(max_ticks):
            if not self.tick():print(f"\n  Budget at T{self.tick_n}");break
            if (t+1)%10==0:
                u=self.llm.usage()
                print(f"  T{self.tick_n}: {len(self.feed)}p {len(self.agents)}a "
                      f"{len(self._langs())}L {len(self._countries())}C ${u['cost_usd']:.4f}")
        dt=time.time()-t0;self._save();u=self.llm.usage()
        types={};media_ct=0
        for p in self.feed.posts:
            t=p.get("meta",{}).get("type","?");types[t]=types.get(t,0)+1
            if p.get("meta",{}).get("media"):media_ct+=1
        follows=sum(len(a.mem.following) for a in self.agents.values())
        edits=sum(len(a.mem.profile_edits) for a in self.agents.values())
        dreams=sum(len(a.mem.dreams) for a in self.agents.values())
        evolved=sum(1 for a in self.agents.values() if a.mem.persona_prompt)
        hist=sum(1 for p in self.feed.posts if p.get("meta",{}).get("is_history"))
        webs=sum(len(a.mem.web_topics) for a in self.agents.values())
        print(f"\n{'='*60}\nSWARM COMPLETE\n{'='*60}")
        print(f"  Time: {dt:.0f}s ({dt/60:.1f}m)")
        print(f"  Agents: {len(self.agents)} | Posts: {len(self.feed)} (hist:{hist} live:{len(self.feed)-hist})")
        print(f"  Types: {types}")
        print(f"  Languages: {len(self._langs())} — {sorted(self._langs())}")
        print(f"  Countries: {len(self._countries())} — {sorted(self._countries())}")
        print(f"  Follows: {follows} | Profile edits: {edits}")
        print(f"  Dreams: {dreams} | Web topics: {webs} | Evolved: {evolved} | Media: {media_ct}")
        print(f"  API: {u['calls']} calls ${u['cost_usd']:.4f} | Parse: {u['parses_ok']}ok/{u['parses_fail']}fail")
        return self._export()

    def _save(self):
        with open(f"{self.out_dir}/swarm_session.json",'w') as f:
            json.dump(self._export(),f,indent=2,ensure_ascii=False)
    def _export(self):
        accts={}
        for a in self.agents.values():
            p=a.persona;b=_badge(p)
            accts[a.id]={
                "id":a.id,"name":p.get("name",a.id),"handle":f"@{a.id}",
                "badge":b.get("badge","none"),"bio":p.get("bio",""),
                "role":p.get("role",""),"style":p.get("style",""),
                "country":p.get("country",""),"lang":p.get("lang","en"),
                "langs":p.get("langs",[]),"followers":p.get("followers",0),
                "following_count":p.get("following",0),
                "joined":p.get("joined",""),"connected_via":p.get("connected_via",""),
                "interests":p.get("interests",[]),
                "username_changes":p.get("username_changes",[]),
                "prev_usernames":p.get("prev_usernames",[]),
                "profile_edits":a.mem.profile_edits,
                "following_users":list(a.mem.following),
                "follower_users":list(a.mem.followers),
                "model":a.model,"turns":a.turn_count,
                "dreams":a.mem.dreams,"life":a.mem.life,
                "web_topics":a.mem.web_topics,
                "evolved_persona":a.mem.persona_prompt,
                "seed_words":p.get("seed_words",[])}
        return {"observations":self.feed.posts,"accounts":accts,
                "stats":{"total_posts":len(self.feed),"total_accounts":len(self.agents),
                         "ticks":self.tick_n,"languages":sorted(self._langs()),
                         "countries":sorted(self._countries()),"api":self.llm.usage()},
                "log":self.log[-500:]}
    def _langs(self):
        L=set()
        for p in self.feed.posts:L.add(p.get("meta",{}).get("lang","en"))
        for a in self.agents.values():
            for l in a.persona.get("langs",[]):L.add(l)
        return L
    def _countries(self):return {a.persona.get("country","") for a in self.agents.values()}-{""}
    def _log(self,msg):
        self.log.append({"tick":self.tick_n,"t":time.time(),"msg":msg})
        print(f"[T{self.tick_n}] {msg}")

def _badge(p):
    if not p:return {}
    b="none"
    if p.get("org_verified"):b="org_gold"
    elif p.get("verified"):b="blue_check"
    elif p.get("legacy_verified"):b="legacy_blue"
    return {"badge":b,"followers":p.get("followers",0),"account_type":p.get("account_type","personal")}

def run_swarm(api_key,budget=5.0,n_seed=10,max_ticks=500,out_dir="./dataset_data"):
    Swarm(api_key,budget,out_dir).run(n_seed,max_ticks)
