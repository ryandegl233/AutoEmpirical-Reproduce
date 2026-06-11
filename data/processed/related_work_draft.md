# AutoEmpirical Related Works Draft

这份 draft 将 AutoEmpirical 放在 automated issue classification、LLM-based software-engineering agents、multi-agent software-engineering workflows，以及更广义的 auto-research systems 这几条研究线中讨论。重点是筛选那些能够支撑 baseline 的工作，用于 GitHub issue report filtering 和 empirical bug-study taxonomy classification。

## Automated Issue Classification

Automated issue classification 是与 AutoEmpirical 最接近的一条 related work，因为它同样把 issue reports 视为 natural-language artifacts，并将其映射到 developer-defined 或 researcher-defined labels。早期系统如 TicketTagger 和 CatIss 主要把 GitHub issue reports 分类为 bug、enhancement 和 question 等 coarse-grained categories，方法上使用 traditional machine-learning 或 transformer-based models。CatIss 尤其值得关注，因为它在大规模 GitHub issue collections 上提供了一个较强的 RoBERTa baseline；后续关于 pre-trained language models 和 data quality 的研究也说明，在 curated labels 可用时，supervised encoder models 仍然具有很强竞争力。

近期以 LLM 为核心的研究把比较对象从 classical classifiers 扩展到 zero-shot 和 prompt-based labeling。关于 issue report classification 的 benchmarking studies 系统评估了多个 generative LLMs 与 BERT-like baselines，并强调 manual labeling cost、inference cost 和 deployment constraints 之间的实际 tradeoff。NASA flight software study 对 AutoEmpirical 尤其有价值，因为它研究 safety-critical issue datasets 中的 bug-ticket identification，并报告 SetFit 在 small curated training sets 上可以超过 zero-shot generative LLMs。Fine-grained bug categorization 进一步研究 prompt engineering 与 LLM label consistency 对详细 bug categories 的影响，这一点直接对应 AutoEmpirical 中的 `symptom`、`root_cause`、`bug_type` 和 `fix_type` labels。

因此，在第一组 baseline 中，AutoEmpirical 至少应该包含三类 non-MAS comparisons：single-agent prompting baseline、RoBERTa/SetFit/CatIss-style fine-tuning 等 supervised encoder baseline，以及 FLAN-T5-style issue classification 这样的 text-to-text generation baseline。这些 baselines 可以检验 MAS architecture 是否确实优于更简单的 prompting，也可以检验在 unified labels 足够时，是否仍然需要 LLM-based classification。

## LLM Agents for Software Engineering

LLM software-engineering agent research 与 AutoEmpirical 不是完全同一个任务，但仍然重要，因为这类工作研究 agents 如何围绕真实 issue reports 进行 reasoning、evidence retrieval、repository interaction 和 validation。SWE-bench 建立了一个用于解决真实 GitHub issues 的 standard benchmark，其任务由 issue-PR pairs 和 fail-to-pass tests 构成。SWE-agent 进一步说明，用于 file navigation、editing 和 test execution 的 agent-computer interface 能够提升 repository-level issue solving。AutoCodeRover 以及关于 LLM-based bug-fixing agents 的 empirical studies 也表明，fault localization、bug reproduction 和 dynamic validation 是 agent 成功的重要因素。

这些工作与 AutoEmpirical 的区别在于，它们的目标是 repair bugs，而不是从 heterogeneous empirical bug-study datasets 中重建 empirical-study labels。不过，它们仍然支持一种 evidence-centered workflow：当 linked PRs、stack traces、code snippets、reproduction steps 和 test evidence 可用时，agents 不应该只依赖 issue text 进行 classification。Agentless 是一个重要的 cautionary baseline，因为它指出 carefully structured non-agent workflows 在某些 software repair tasks 上可以达到甚至超过复杂 autonomous agents。因此，AutoEmpirical 在宣称 multi-agent design 是主要改进来源之前，应该把 full MAS behavior 与 staged single-agent workflows 进行比较。

## Multi-Agent Research and Software Workflows

Multi-agent software frameworks 为 AutoEmpirical 的 Evidence、Filter、Symptom、Root Cause、Critic 和 Arbitrator roles 提供了设计依据。ChatDev 将 software development 分解为跨 design、coding、testing 和 documentation 的 role-based communicative agents。MetaGPT 将 standardized operating procedures 引入 collaborative LLM workflows，以减少 cascading hallucinations。Self-collaboration code generation 也使用 analyst、coder 和 tester roles，相比 single LLM agent 提升 code-generation performance。

AutoEmpirical 与这类工作的联系主要是 methodological：empirical-study task 可以被建模为 structured research workflow，而不是一次性的 classification call。Evidence Agent 负责抽取 observed facts，classifier agents 独立做 label decisions，Critic Agent 检查这些 decisions 是否被 evidence 和 taxonomy definitions 支撑，Arbitrator Agent 则把候选结果融合为一个 structured decision。这种设计类似 SOP-style multi-agent systems，但将 roles 从 software construction 调整到了 empirical software fault analysis。

## Multi-Agent Research/Survey Automation

更广义的 auto-research systems 对 AutoEmpirical 的 related-work 整理和 research synthesis 部分有参考价值。ResearchAgent 结合 literature retrieval、academic graphs、knowledge stores 和 reviewer agents，用于生成并迭代 research ideas。AutoSurvey 通过 retrieval、outline generation、subsection drafting、integration 和 evaluation 来自动生成 literature surveys。STORM 在 retrieval 和 writing 之前进行 multi-perspective question asking，从而提升内容的 breadth 和 organization。The AI Scientist 则是更广义的 end-to-end research automation framework，包含 idea generation、experiments、paper writing 和 simulated review。

这些 systems 与 AutoEmpirical 的 issue-labeling task 相比没有那么直接，但它们提供了可复用的 design patterns：retrieval 应该显式化，synthesis 前应该先生成 outlines，reviewer/critic agents 应该评估 coverage 和 evidence grounding。对于当前 AutoEmpirical paper，这些工作更适合作为 broader auto-research context，放在更核心的 issue-classification 和 software-agent literature 之后讨论。

## Gap and Positioning

现有 issue-classification studies 主要关注 bug、enhancement 和 question 等 coarse labels，或者在单一 benchmark dataset 上评估 model performance。LLM bug-fixing agents 关注通过修改代码来 resolve issues，而不是从 heterogeneous paper datasets 中重建 empirical-study labels。Multi-agent software frameworks 说明 role specialization 可以支持复杂 workflows，但它们很少直接面向 empirical software engineering research tasks。

AutoEmpirical 的 gap 在于，它将 empirical software fault analysis 建模为 unified issue-level datasets 上的 structured agent workflow。它结合 evidence extraction、defect filtering、fine-grained taxonomy classification、critique 和 arbitration，处理来自多个 empirical bug studies 的 records。最稳妥的论点不应该是 MAS 总是更好，而应该是：reliability-oriented MAS 可以在 unified empirical bug-study corpus 上，与 single-agent prompting、self-consistency/voting 和 supervised issue-classification baselines 进行系统比较。

## Baseline Directions to Run Next

- **Single-agent prompting**: 一个 LLM 接收 title、body、comments 和 taxonomy definitions，然后输出完整 JSON label。
- **Multi-agent role decomposition**: Evidence、Filter、Symptom、Root Cause、Critic 和 Arbitrator agents 复现当前 AutoEmpirical workflow。
- **LLM vs BERT/SetFit issue classifier**: 将 zero-shot/few-shot LLM filtering 与基于 `stage1_unified_labels.csv` 训练的 lightweight supervised encoder 进行比较。
- **Self-consistency / majority vote**: 在不使用完整 role specialization 的情况下采样多个独立 LLM outputs，用于区分性能提升来自 voting 还是 role design。

## Sources Used

- Benchmarking large language models for automated labeling: https://doi.org/10.1016/j.infsof.2025.107758
- NASA issue classification with LLMs: https://www.sciencedirect.com/science/article/pii/S0164121226000853
- Fine-grained bug report categorization with LLMs: https://doi.org/10.1145/3736408
- CatIss: https://doi.org/10.1145/3528588.3528662
- SWE-bench: https://arxiv.org/abs/2310.06770
- SWE-agent: https://arxiv.org/abs/2405.15793
- Agentless: https://arxiv.org/abs/2407.01489
- ChatDev: https://arxiv.org/abs/2307.07924
- MetaGPT: https://arxiv.org/abs/2308.00352
- ResearchAgent: https://arxiv.org/abs/2404.07738
- AutoSurvey: https://arxiv.org/abs/2406.10252
- STORM: https://arxiv.org/abs/2402.14207
