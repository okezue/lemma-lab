# LEMMA Lab

LEMMA Lab is a recursive, prior-building research system that treats investigation the way a mathematician treats a proof. User queries become conjectures, candidate explanations become hypotheses, tools become tactics, evidence becomes proof objects, and stable insights become reusable priors in a growing theorem library. The system is not centered on agent conversations. It is centered on a shared epistemic substrate that accumulates structured knowledge across runs.

## How it works

The core idea is that research memory should not be a chat log or a rolling summary. It should be a proof state. The system maintains a six-layer recursive context: a raw observation ledger, a claim graph with typed support and contradiction edges, branch capsules that compress working memory without losing open questions, an agenda capsule for global scheduling, a prior library of reusable beliefs with scope and transfer scores, and an anti-prior bank of known cognitive traps to avoid.

When a conjecture enters the system, a hypothesis generator proposes 3-7 candidate explanations, each with testable predictions and specific falsifiers. A dispatcher scores these by expected information gain and assigns them to parallel branches. For each branch, a prover agent searches the actual dataset using primitive tools (keyword search, timeline construction, thread reconstruction, paper content retrieval, figure analysis) and builds supporting claims grounded in real evidence. A breaker agent simultaneously searches for counterevidence, checks source credibility, identifies smuggled assumptions, and proposes alternative explanations. Both agents see the existing claim graph to avoid duplicates and can link new claims to existing ones via typed edges.

After each prove/break cycle, an auditor checks whether the branch actually earned its conclusion by examining citation quality, evidence strength, and ignored contradictions. Branches that pass with high confidence get their hypotheses proved and automatically promoted to priors. Branches that fail get broken. A capsule compressor then summarizes the branch state, preserving the full evidence trail and open questions in an 800-character capsule that future agents can reference without reloading the entire context.

Every few steps, a toolsmith analyzes tool usage traces and proposes new composite tools that chain existing primitives. These get registered as executable functions, not just metadata. A prior editor agent periodically reviews all active priors against the current claim graph, strengthening priors with new evidence, weakening ones that have counterexamples, creating new priors from stable patterns, demoting priors that are wrong, and creating anti-priors as warnings about reasoning traps. When a prior is demoted, proof repair kicks in: dependent claims are marked stale, affected branches have their confidence halved, and they get re-queued for investigation.

An analyst agent can run statistical analysis on the full dataset, generate graph specifications for visualization, and fact-check existing claims against actual data distributions.

## Autonomous research

The system does not require human-injected conjectures. An autonomous researcher scans the loaded corpus, identifies patterns and tensions, generates its own theses, investigates them through the full pipeline, and saves findings as priors. Each subsequent round of thesis generation sees the accumulated priors and previous run history, so it builds on or cross-tests earlier findings rather than repeating them. In our test run, the system autonomously conducted 9 investigations across 3 rounds on a 7,507-post corpus, accumulating 145 claims, 40 reusable priors, and 10 anti-priors, with one prior being demoted mid-session and two branches reopened for proof repair.

## The swarm

LEMMA Lab includes a fully agentic X/Twitter simulation that generates the research corpus. Each agent is born from random seed words (fetched from a dictionary API), dreams up a life history, builds historical posts, and then participates in a live simulation. Agents have personalized algorithmic feeds weighted by language affinity, following relationships, shared interests, and geographic proximity. They can post, reply, quote, retweet, scroll profiles, follow each other, edit their profiles, and discover topics via web search. An observer agent periodically reads an agent's post history and writes an evolved persona description that becomes its new system prompt.

The simulation uses varying temperatures and randomly sampled models across personas for stochastic diversity. Agents don't have to respond to everything; engagement probability depends on language match, follow status, and energy levels with cooldown. Reply loops are capped, and agents are nudged toward original posts about their own lives rather than endless reaction chains. Notifications from @mentions propagate to the mentioned agent, who may or may not respond depending on language affinity and current energy.

Our production run generated 7,507 posts from 543 agents across 82 countries in 110 languages for $1.91 in API costs.

## Architecture

The epistemic substrate has six layers. Layer 0 is the research ledger, an append-only store of raw observations queryable by source, modality, time, and keyword. Layer 1 is the claim graph, where normalized assertions carry support, contradiction, and dependency edges with confidence scores that propagate automatically. Layer 2 holds branch capsules, which are per-hypothesis working memory objects tracking supporting and contradicting claim IDs, assumptions, pending actions, prior dependencies, inter-branch dependencies, and temporal belief trajectories. Layer 3 is the agenda capsule, a compressed global view of active, stalled, and tension-heavy branches. Layer 4 is the prior library, where each prior has a type (domain, source, or procedural), a scope, assumptions, supporting evidence, counterexamples, a transfer score, and failure cases. Layer 5 is the anti-prior bank, storing reusable warnings about previously tempting but disproven reasoning patterns.

Ten agents operate on this substrate. The hypothesis generator scans available data and proposes discriminating candidates with predictions and falsifiers. The prover searches the dataset using 19 primitive tools, analyzes found evidence against existing claims, and links new claims into the graph. The breaker searches for counterevidence with anti-keywords, audits source credibility, and identifies smuggled assumptions. The multimodal scout inspects artifacts (figures, charts, tables) blind, without surrounding narrative, to prevent anchoring. The auditor verifies that branches earned their conclusions. The toolsmith proposes and registers executable composite tools from repeated patterns. The synthesizer produces final reports separating object-level truth from narrative-level belief. The prior editor actively manages the prior library. The analyst runs statistical analysis and generates visualization specs. The dispatcher orchestrates all of this with priority scoring, temporal belief tracking, and proof repair.

The tool library has 19 primitives (search by keyword, source, modality, day, persona; thread and quote chain reconstruction; paper and figure content retrieval; source credibility checks; contradiction finding; claim comparison; bot detection; repost trees; temporal snapshots) and 8 composite tools (coverage gap detection, narrative vs evidence volume comparison, appendix headline cross-checking, rumor origin tracing, quote chain language shift detection, figure claim linking, benchmark version diffing, and quote chain timeline analysis). The toolsmith can create more at runtime.

## Running it

Set your xAI API key and install dependencies.

```
pip install -r requirements.txt
export XAI_API_KEY="your-key"
```

Generate the Polyglot Proof Crisis dataset from the handcrafted world specification (125 personas, 66 countries, 75 languages).

```
python main.py --mode generate
```

Or run the agentic swarm simulation to generate a fully synthetic corpus.

```
python main.py --mode swarm --budget 5.0 --seed-agents 15 --max-ticks 500
```

Run the autonomous researcher on any dataset. It will scan the corpus, generate its own theses, investigate them, and accumulate priors across rounds.

```
python main.py --mode research --dataset ./dataset_data/swarm_session.json --budget 2.0
```

Or start the interactive REPL for manual investigation.

```
python main.py --mode repl --dataset ./dataset_data/polyglot_crisis.json
```

The REPL supports 31 commands: ask, run, step, agenda, spawn, challenge, inspect, promote, demote, priors, claims, tools, tool, report, save, load_dataset, log, toolize, usage, stats, scout, analyze, edit_priors, snapshot, metrics, repairs, fetch, and quit.

Run a single investigation directly.

```
python main.py --mode ask --query "Was the breakthrough real?" --dataset ./dataset_data/polyglot_crisis.json --steps 5
```

Run the full benchmark comparing context ablations and model variants.

```
python main.py --mode benchmark --dataset ./dataset_data/polyglot_crisis.json
```

All state (ledger, claim graph, priors, run history) persists to JSON and carries across sessions. Future runs inherit accumulated knowledge.

## Models

All reasoning uses `grok-4-fast-reasoning` via the xAI API. Vision uses `grok-2-vision-1212`. The swarm randomly samples across `grok-4-fast-non-reasoning`, `grok-3`, and `grok-3-mini` for persona stochasticity. Cost tracking is built in at the per-model level.
