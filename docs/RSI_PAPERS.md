# RSI 论文清单 · DWC

> **19 篇**，标题与摘要均自 `arxiv.org/abs/<id>` 逐一抓取核实（2026-10-02）。
> 来源：ARSI 项目全量引用（`src/` 148 文件 + README + PROGRESS.md）。

> 本清单只列事实（标题/摘要/编号），不含取舍判断。

---


## I. 递归自我改进 · 总论与框架


### `2609.13406` — Generalized Agent Iteration: One Formal Framework for Iterative Policy Improvement and Recursive Self-Improvement

*分类*: Artificial Intelligence (cs.AI)

**摘要**

> When we speak of recursive self-improvement (RSI), are we speaking of a phenomenon, a mechanism, or a prospect? Towards autonomous and evolving intelligence, RSI is being claimed at many scales, while no single framework that formally describes these emerging instances exists. Its counterpart in the classical realm, iterative policy improvement, is characterized by generalized policy iteration (GPI), a framework of broad applicability with well-understood theoretical properties, but only where the update principle and the evaluation base lie outside the agent. In this paper, we propose Generalized Agent Iteration (GAI), a formal framework that describes iterative policy improvement and RSI as two cases of a single learning paradigm. GAI defines the agent as a configuration of modifiable components within a system and models the learning process as a cycle of agent evaluation and agent improvement. Two pivotal dials then distinguish the instances: whether the improving mechanism is part of the agent and whether the standard it is measured against is grounded outside it. The former dia


### `2609.14857` — ModularRSI: Modular and Generalizable Recursive Harness Self-Improvement

*分类*: Computation and Language (cs.CL)

**摘要**

> Recent work extends recursive self-improvement (RSI) to agent harnesses for long-horizon coding and terminal tasks, enabling agents to improve execution mechanisms from experience. However, generalizable harness RSI remains challenging. First, evolving harnesses on evaluation benchmarks or their subsets makes it difficult to distinguish reusable improvements from benchmark-specific adaptation. Second, single-trajectory updates can conflate systematic harness deficiencies with instance-specific reasoning and solution details, producing modifications that transfer poorly to unseen tasks. Third, localizing recurring behavioral deficiencies within monolithic harnesses is difficult, while whole-harness optimization can entangle unrelated mechanisms and complicate attribution and validation. We propose ModularRSI, a benchmark-disjoint, contrastive, and modular framework for generalizable harness evolution. ModularRSI contrasts successful and failed trajectories for the same task and aggregates evidence across tasks to identify recurring behavioral deficiencies. It decomposes the evolvable 


### `2609.11873` — The Last AI Built by Humans: Toward Genuine Recursive Self-Improvement

*分类*: Machine Learning (cs.LG)

**摘要**

> Recursive self-improvement (RSI) enables AI systems to turn experience and feedback into persistent changes that improve both their capabilities and the process of future improvement. We first use the Headroom-Closed Index (HCI) to reveal the problems of existing LLMs, then introduce the RSI concept and its development roadmap: from improvement-execution autonomy, improvement-strategy autonomy, experience-acquisition autonomy, and environment-adaptation autonomy, to recursive meta-improvement. Next we examine RSI across scenarios (e.g., scientific discovery, embodied intelligence, software engineering), highlighting their distinct requirements and development speeds. Drawing on diverse industry practices and preliminary empirical evidence, we connect RSI research with practical systems and identify key challenges to achieving genuine RSI.


### `2609.06396` — MetaRSI / RSI2: A Meta-Recursive Self-Improving System for Recursive Self-Improving Systems Themselves

*分类*: Machine Learning (cs.LG)

**摘要**

> Recursive self-improvement (RSI) lets a system improve the model-building machinery from its own failures, so every later model inherits the gain. Yet RSI has been validated almost exclusively on coding and formal benchmarks such as science QA and mathematics. This format bound limits RSI to improvement within a machine-checkable slice, not general capability where questions are open and correctness is settled by argument, replication, or measurement. We argue RSI must next operate across real, diverse scientific, engineering, and meta-scientific domains, not where formal evaluation is merely tractable. To that end we present MetaRSI-v1, where improvement is the scheduled composition of three typed operators over one unified paradigm. Data-RSI amplifies existing competence and marks its boundary; Harness-RSI edits a five-slot scaffold without touching weights; Model-RSI internalizes capability into parameters through bounded training. Sharing one loop kernel and artifact vocabulary, they make data, scaffold, and model changes composable rather than exclusive. A two-axis optimizer joi


## II. Harness 自进化（智能体外壳自改进）


### `2606.14249` — HarnessX: A Composable, Adaptive, and Evolvable Agent Harness Foundry

*分类*: Artificial Intelligence (cs.AI)

**摘要**

> AI agent performance depends critically on the runtime harness, comprising the prompts, tools, memory, and control flow that mediate how a model observes, reasons, and acts. Yet today&#39;s harnesses remain largely hand-crafted and static: each new model or task still demands bespoke scaffolding, and the rich traces produced during execution are rarely distilled back into systematic improvement. We introduce HarnessX, a foundry for composable, adaptive, and evolvable agent harnesses. HarnessX assembles typed harness primitives via a substitution algebra, adapts them through AEGIS, a trace-driven multi-agent evolution engine grounded in an operational mirror between symbolic adaptation and reinforcement learning, and closes the harness-model loop by turning trajectories into both harness updates and model training signal. Across five benchmarks (ALFWorld, GAIA, WebShop, tau^3-Bench, and SWE-bench Verified), HarnessX yields an average gain of +14.5% (up to +44.0%), with gains largest where baselines are lowest. These results suggest that agent progress need not come from model scaling 


### `2606.09498` — Self-Harness: Harnesses That Improve Themselves

*分类*: Computation and Language (cs.CL)

**摘要**

> The performance of LLM-based agents is jointly shaped by their base models and the harnesses that mediate their interaction with the environment. Because different models exhibit distinct behaviors, effective harness design is inherently model-specific. Yet agent harnesses are still largely engineered by human experts, a paradigm that scales poorly as modern LLMs become increasingly diverse and rapidly evolving. In this paper, we introduce Self-Harness, a new paradigm in which an LLM-based agent improves its own operating harness, without relying on human engineers or stronger external agents. We operationalize Self-Harness as an iterative loop with three stages: Weakness Mining, which identifies model-specific failure patterns from execution traces; Harness Proposal, which generates diverse yet minimal harness modifications tied to these failures; and Proposal Validation, which accepts candidate edits only after regression testing. We instantiate Self-Harness across Terminal-Bench-2.0, SWE-bench Verified, and AppWorld using a minimal initial harness and three base models from divers


### `2609.14858` — Dream-RSI: Recursive Self-Improvement through Evolving Worlds

*分类*: Computation and Language (cs.CL)

**摘要**

> Recursive self-improvement is becoming increasingly vital for autonomous AI agents, where progress hinges on discovering high-value solutions across complex domains. The driver of this process is effective exploration, however, managing and improving exploration strategies remains a major bottleneck. Current systems face a fundamental dilemma: fixed strategies fail to adapt as search spaces scale, while online policy optimization requires navigating vast meta-search spaces under delayed and expensive feedback over long-horizon rollouts. We introduce \textsc{Dream-RSI}, a framework for scalable and recursively self-improving exploration. A lightweight orchestration layer makes exploration explicit and programmable while leaving the underlying coding agent unchanged. Our key insight is that accumulated discovery history can serve as a replay simulator over the realized search space. By performing dreaming in the replay simulator constructed from historical discovery trees, \textsc{Dream-RSI} secures immediate, low-cost off-policy feedback to evaluate and refine exploration policies wit


### `2505.05522` — Continuous Thought Machines

*分类*: Machine Learning (cs.LG)

**摘要**

> Biological brains demonstrate complex neural activity, where neural dynamics are critical to how brains process information. Most artificial neural networks ignore the complexity of individual neurons. We challenge that paradigm. By incorporating neuron-level processing and synchronization, we reintroduce neural timing as a foundational element. We present the Continuous Thought Machine (CTM), a model designed to leverage neural dynamics as its core representation. The CTM has two innovations: (1) neuron-level temporal processing, where each neuron uses unique weight parameters to process incoming histories; and (2) neural synchronization as a latent representation. The CTM aims to strike a balance between neuron abstractions and biological realism. It operates at a level of abstraction that effectively captures essential temporal dynamics while remaining computationally tractable. We demonstrate the CTM&#39;s performance and versatility across a range of tasks, including solving 2D mazes, ImageNet-1K classification, parity computation, and more. Beyond displaying rich internal repre


## III. 评估 · 环境演化 · 判分


### `2609.04128` — Environment Evolution for Terminal Agents

*分类*: Artificial Intelligence (cs.AI)

**摘要**

> Scaling interactive and verifiable environments is critical for training terminal agents. As frontier models become more capable, environments synthesized from scratch become less challenging and thus provide limited learning signals. Recent co-evolution methods iteratively synthesize environments near the model&#39;s learnable frontier based on weaknesses exposed during rollouts. However, their dependence on on-policy rollouts limits generalization and the continuous provision of learning signals as the model becomes stronger. In this paper, we propose environment evolution, which incrementally increases environment difficulty off-policy and schedules the evolved environments generation by generation during training to provide continuous learning signals. We derive three evolution directions that influence environment difficulty from the multi-turn learning objective and then implement evolution along these directions through a loop-engineered multi-agent harness. Quantitative rollout experiments with Hy4 preview, Claude Opus 5, and GPT-5.6 Sol show that environment evolution consis


### `2607.12790` — Who Grades the Grader? Co-Evolving Evaluation Metrics and Skills for Self-Improving LLM Agents

*分类*: Artificial Intelligence (cs.AI)

**摘要**

> Self-evolving agent systems create, revise, and retire their own skills, but every such loop assumes a reliable evaluation metric already exists. In many real applications none does. We show the metric itself can be the evolving object: our loop searches compositions of small typed drawback detectors under a full evolutionary lifecycle, selecting for agreement with a ten-item anchored reference set and regularizing by consensus over unlabeled outputs. What evolves is the function that grades one output, never the fixed task sets it is scored on, and what comes out is an inspectable expression rather than an opaque judge. It is also valid: on code generation it gains 0.21 agreement with hidden ground truth on a locked set that metric selection never reads (paired $p=0.014$), beating the bare LLM judge it contains. Validity is where safety lives: removing the anchor guards collapses the metric into a vacuous always-pass detector while removing the detector lifecycle does not, inverting the lesson from skill evolution. That collapse warns this line of work that downstream task score can


### `2609.08183` — NeoHorse-1: Towards Recursive Self-Improvement via Agentic Post-Training with Routing Harness

*分类*: Computation and Language (cs.CL)

**摘要**

> Recursive self-improvement (RSI) requires a concrete mechanism through which an AI system observes its capabilities and converts that evidence into the next round of learning. We present NeoHorse-1, a family of agent-native models developed to explore this path through agentic post-training. Our system combines a heterogeneous model pool with intelligent routing, recording the predicted capability demand, selected service tier, and subsequent interaction for each user turn. These records are converted into training examples that preserve interleaved reasoning, tool calls, and harness context, and are admitted through structural validation, six-dimensional semantic evaluation, and subscene-level labeling. Routing signals organize supervised fine-tuning into a three-stage curriculum and extend to routing-guided on-policy distillation, where a teacher supervises student-generated responses under the same progression. Capability-guided allocation then converts evaluation feedback into the next training mixture, closing an evaluation-selection-update loop in which what the system learns t


### `2609.26457` — Recursive self-improvement of AI research agents

*分类*: Artificial Intelligence (cs.AI)

**摘要**

> AI agents are beginning to automate research and development across the AI stack, from improving training efficiency to optimizing inference. A natural next step is to improve the research efficiency of the agents themselves. When an AI research agent&#39;s own code is the object of optimization, each accepted rewrite becomes the agent that the next round edits. We refer to this loop as recursive self-improvement. Its significance lies in a long-standing trend, in which increased cumulative spending on R&amp;D yields diminishing returns. Sustained self-improvement offers a way to counter this trend. We present AIDE^2, a system that implements this loop for a frontier AI research agent. It proposes changes to its own code, benchmarks modified versions of itself on a suite of AI R&amp;D tasks, and keeps the changes that perform best on hidden evaluations. In an autonomous 8-day run, AIDE^2 discovered seven successive improvements, ranging from a new search policy to memory mechanisms that compress and manage the agent&#39;s growing context. These gains generalize to four held-out bench


## IV. 世界模型 / 自我建模


### `2607.27201` — Mental World Modeling

*分类*: Computation and Language (cs.CL)

**摘要**

> World models enable a predictive substrate for planning and action, yet existing formulations merely answer a physical question: what/where it is, and how will it evolve. Human behavior, however, is driven by hidden mental state (what a person believes, wants, intends, feels, and considers socially permissible), so a model that tracks the physical scene but not what each agent knows and believes about it predicts the wrong action for the right-looking scene. We formulate Mental World Modeling (MWM), a generic theoretical framework that makes mental variables core components of a world model rather than posthoc rationales: MWM aintains a coupled physical-mental world state, renders a target-specific partial observation, and simulates how candidate actions jointly update both components. We instantiate the framework in MENTIS, a training-free and fully inspectable baseline that decomposes the process into state parsing, target-observation generation, action decomposition, coupled physical and mental transition, and branch-level value evaluation. On a manually constructed, quality-contr


### `2607.27924` — ODEWorld: A Continuous Predictive Architecture via Physical-Time Flow

*分类*: Machine Learning (cs.LG)

**摘要**

> In the physical world we inhabit, space and time are fundamentally continuous. However, existing machine learning paradigms for world modeling are largely confined to discrete-time prediction, thereby exhibiting significant inefficiency in capturing the dynamics of physical world. We introduce Physical-Time Flow (PT-Flow), a novel approach that learns a continuous latent velocity field operating in physical time. Crucially, the underlying dynamics of sequential data are parameterized by an ordinary differential equation (ODE) embedded in a well-structured representation space. Under this paradigm, the prediction of future can be recast as temporal integration via an ODE solver in the compressed latent space. Building upon PT-Flow, we construct ODEWorld, a continuous-time latent world model that is both efficient and versatile. By extracting time-variant features and enforcing ODE properties on both the dynamical representation space and the latent velocity field, ODEWorld effectively addresses the long-standing representation collapse issue in latent world model literature. This also


### `2608.24876` — Recursive Experiential-Working Memory Evolution for Long-Horizon Agent Harnesses

*分类*: Artificial Intelligence (cs.AI)

**摘要**

> Recursive self-improvement (RSI) remains hard in long-horizon tasks, where growing histories obscure the task state and misalign skill invocation. We introduce Recuris, a recursive Experiential-Working Memory architecture for long-horizon agent harnesses, in which Working Memory tracks task progress and guides skill selection from Experiential Memory, grounding skill use in current needs rather than the full history. This coupling also turns execution into structured evidence that localizes failures to specific memory components. Across tasks, a fixed Meta-Agent turns that evidence into localized, validation-gated updates to Skill Memory that reshape execution and yield new evidence, forming a bounded recursive memory-evolution loop. Across four long-horizon benchmarks and ten models, Recuris improves task success in 35 of the 37 completed model-benchmark pairs, carrying frontier models to SOTA-level task success: on tau-bench it adds +17.8 points to GPT-5.6 Sol and +15.6 to Claude Opus 5, taking Opus 5 to 87.9%, and +16.6/+13.5 points on Qwen3.6-27B/35B on SkillFlow. The advantage w


## V. 契约· 护栏 · 安全


### `2603.25111` — SEVerA: Verified Synthesis of Self-Evolving Agents

*分类*: Machine Learning (cs.LG)

**摘要**

> Recent advances have shown the effectiveness of self-evolving LLM agents on tasks such as program repair and scientific discovery. In this paradigm, a planner LLM synthesizes an agent program that invokes parametric models, including LLMs, which are then tuned per task to improve performance. However, existing self-evolving agent frameworks provide no formal guarantees of safety or correctness. Because such programs are often executed autonomously on unseen inputs, this lack of guarantees raises reliability and security concerns. We formulate agentic code generation as a constrained learning problem, combining hard formal specifications with soft objectives capturing task utility. We introduce Formally Guarded Generative Models (FGGM), which allow the planner LLM to specify a formal output contract for each generative model call using first-order logic. Each FGGM call wraps the underlying model in a rejection sampler with a verified fallback, ensuring every returned output satisfies the contract for any input and parameter setting. Building on FGGM, we present SEVerA (Self-Evolving V


### `2603.06333` — SAHOO: Safeguarded Alignment for High-Order Optimization Objectives in Recursive Self-Improvement

*分类*: Artificial Intelligence (cs.AI)

**摘要**

> Recursive self-improvement is moving from theory to practice: modern systems can critique, revise, and evaluate their own outputs, yet iterative self-modification risks subtle alignment drift. We introduce SAHOO, a practical framework to monitor and control drift through three safeguards: (i) the Goal Drift Index (GDI), a learned multi-signal detector combining semantic, lexical, structural, and distributional measures; (ii) constraint preservation checks that enforce safety-critical invariants such as syntactic correctness and non-hallucination; and (iii) regression-risk quantification to flag improvement cycles that undo prior gains. Across 189 tasks in code generation, mathematical reasoning, and truthfulness, SAHOO produces substantial quality gains, including 18.3 percent improvement in code tasks and 16.8 percent in reasoning, while preserving constraints in two domains and maintaining low violations in truthfulness. Thresholds are calibrated on a small validation set of 18 tasks across three cycles. We further map the capability-alignment frontier, showing efficient early impr


## VI. 共演化


### `2608.10299` — Co-Evolution in Agentic Systems: Toward Self-Directed Evolution Beyond Human Design

*分类*: Computation and Language (cs.CL)

**摘要**

> Agentic systems are increasingly expected to improve after deployment, yet single-entity self-evolution is often bounded by a static learning context, such as fixed tasks and feedback. This survey focuses on co-evolution in agentic systems, a multi-component form of self-evolution in which multiple agents and their environment impose adaptive pressure on one another. To organize existing papers, we propose a progressive three-stage taxonomy that traces how the system gradually sheds human-engineered constraints. Agent--Agent Co-Evolution studies how agents adapt through dynamic peers, including adversarial, collaborative, and organizational adaptation. Agent--Environment Co-Evolution extends this loop to adaptive tasks, feedback, and interaction spaces that change with the agents. Meta Co-Evolution further explores the possibility of making the evolution mechanism itself evolvable. We also discuss open challenges in evaluating such systems, scaling them across multiple components, and keeping increasingly autonomous evolutionary processes safe and controllable. This survey provides a


## VII. 正则化 / 元层


### `2609.24972` — RRSI: Regularized Recursive Self-Improvement of Agent Harnesses

*分类*: Machine Learning (cs.LG)

**摘要**

> An LLM agent&#39;s capability is largely magnified by its harness, namely the prompts, control flow, tooling, memory, and context management surrounding the frozen backbone model. Recent methods increasingly automate this process by iteratively proposing and selecting component-wise edits of an agent harness, practically establishing a form of recursive self-improvement (RSI) at the agent-system level. However, such recursive evolution may overfit by memorizing the training tasks, showing large in-distribution gains that shrink or even vanish on out-of-distribution benchmarks. We introduce Regularized Recursive Self-Improvement of Agent Harnesses (RRSI), which incorporates the principles of regularizations into harness self-improvement by constraining the evolution candidate proposal and selection. The proposer operates with a temporally annealed budget, limiting how many edits a candidate can bundle, and it encourages unexplored trajectories based on evolution history. The selector is equipped with a critic and a pruner: the critic screens benchmark-specific proposals, while the pru


---

## 可复现的核实命令

```bash
# 逐篇取标题+摘要
for id in 2609.13406 2609.24972 ... ; do
  curl -sL -A "Mozilla/5.0" https://arxiv.org/abs/$id \
    | grep -oP '(?<=Title:</span>)[^<]+'
done

# 全量提取 ARSI 引用（无遗漏）
cd E:/ARSI && grep -rhoE '2[56][0-9]{2}\.[0-9]{4,5}' src/ docs/ README.md | sort -u
```