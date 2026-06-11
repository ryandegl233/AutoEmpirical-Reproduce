# AutoEmpirical MAS 全量设计文档 v1

> 本文档整合 AutoEmpirical 项目的 Stage 2（Bug Commit 提取）与 Stage 3（多标签分类与总结）的多智能体系统（MAS）设计，涵盖方法论层面（论文写作参考）与协议层面（代码实现参考）的完整规格，并结合实际数据集 `data/processed/stage1_unified_labels.csv` 的统计特征驱动设计决策。

---

## 一、项目背景与数据集分析

### 1.1 任务定义

AutoEmpirical 的目标是从 GitHub issue 数据中自动复现人工实证研究的标注流程，输出符合学术分类体系的结构化 bug 标签。整体流水线分为三阶段：

| 阶段 | 任务 | 状态 |
|------|------|------|
| **Stage 1** | 数据集构建：从 8 篇论文中整合 GitHub issue 数据并标准化 | ✅ 已完成 |
| **Stage 2** | Bug Commit 提取：过滤非 bug issue，提取关联 commit/PR 证据 | 🔧 本文设计 |
| **Stage 3** | 多标签分类：为确认 bug 输出 symptom、root_cause、bug_type、fix_type | 🔧 本文设计 |

### 1.2 数据集统计分析

**数据来源：** `data/processed/stage1_unified_labels.csv`，总计 **1,907 条**记录，来自 8 篇论文、8 个 source project。

**文本可用性（直接影响 Stage 2 设计）：**

| 文本类型 | 记录数 | 占比 |
|----------|--------|------|
| 仅有 title（无 body/comments） | 875 | **45.4%** |
| 有 body | 1,027 | 53.9% |
| 有 comments | 680 | 35.7% |
| body + comments 均有 | 675 | **35.4%** |

⚠️ **关键挑战**：近半数记录（875/1,907）仅有标题，无法利用 body 或 comments 进行常规证据提取，Stage 2 必须为 "title-only" 记录设计专门的处理路径。

**按来源论文的文本可用性：**

| paper_id | body 可用率 | 特征 |
|----------|------------|------|
| ase2021, fse2023, icse2022_perf, icse2023 | **0%** | 极度贫文本：仅凭 title 判断 |
| ase2022, fse2021 | 98–99% | 文本丰富 |
| icse2022_wechat, icse2024 | **100%** | 文本最丰富 |

**标签完整性（直接影响 Stage 3 设计）：**

| 标签组合 | 记录数 | 占比 |
|----------|--------|------|
| 全 4 项标签均有（symptom + root_cause + bug_type + fix_type） | 784 | 41.1% |
| 缺 fix_type | 753 | 39.5% |
| 缺 bug_type | 334 | 17.5% |
| 仅有 symptom（最少标签） | 少量 | — |

**Label Taxonomy 异构性（直接影响 Stage 3 SOP 设计）：**

来自不同论文的标签在命名上高度不一致，同一概念存在多种写法：

| 字段 | 来源论文 | 示例标签值 |
|------|---------|-----------|
| symptom | ase2022 | `Crash`、`Incorrect Functionality`、`Build & Initialization Failure` |
| symptom | **fse2021** | `"Unable to create datasets using the python API after upgrading keras to 2.4.0."` （**全文描述而非分类**） |
| root_cause | ase2022 | `Incorrect Code Logic`、`API Misuse`、`Dependency Error` |
| root_cause | icse2022_wechat | `logic error`、`concurrency issue` |
| bug_type | fse2021 | `hang`、`crash`、`incorrect`、`memory`（4类简写） |

⚠️ **关键挑战**：fse2021 等论文的 symptom 字段包含自由文本描述，而非分类标签，Stage 3 的 Taxonomy Normalizer 必须能够处理这种异构性。

**高频标签分布（Stage 3 Taxonomy 设计参考）：**

Top symptom: Crash (616), Incorrect Functionality (186), Build & Initialization Failure (141), performance bug (137)

Top root_cause: Incorrect Code Logic (159), API Misuse (73), Dependency Error (61)

### 1.3 设计挑战总结

基于数据集分析，提炼出驱动后续 MAS 设计的 6 个核心挑战：

| ID | 挑战 | 影响阶段 |
|----|------|---------|
| **C1** | 45% 记录仅有 title，证据极为贫乏 | Stage 2, Stage 3 |
| **C2** | 标签 taxonomy 高度异构（8 篇论文 × 不同命名体系）| Stage 3 |
| **C3** | fix_type 缺失率高达 39.5%，难以学习 | Stage 3 |
| **C4** | symptom-root_cause 因果逻辑一致性无法从单视角保证 | Stage 3 |
| **C5** | 非 bug issue（feature request、使用问题）混入数据集 | Stage 2 |
| **C6** | LLM 输出在相同 prompt 下具有不确定性，从未被系统追踪 | Stage 2, Stage 3 |

---

## 二、现有方法的局限性分析

### 2.1 现有自动化标注工具的核心缺陷

基于对 15+ 篇相关文献的系统梳理，现有方法存在六类核心局限：

| # | 问题描述 | 代表文献 |
|---|----------|---------|
| **L1** | **高误报率**：自动标注的假阳性率高达 8%–54%，即使 benchmark F1 看起来不错 | Dunivin et al. arXiv:2601.09905 |
| **L2** | **训练数据噪声**：现有 bug 数据集中约 33% 的标签本身错误（feature request 被标为 bug 等）| Laiq & Dobslaw arXiv:2505.01469 |
| **L3** | **提示敏感性与非确定性**：同一 issue 同一 prompt 不同运行产生不同标签；一致性从未被系统追踪 | OLAF, arXiv:2512.15979; Baltes et al. arXiv:2508.15503 |
| **L4** | **模糊/不完整 issue 无处理机制**：几乎所有系统把模糊报告当作噪声丢弃，而不是显式标记 | Laiq arXiv:2505.01469; Gon et al. arXiv:2605.17561 |
| **L5** | **级联错误**：线性流水线中上游角色的错误向下游传播，Arbitrator 无法纠正已丢失信息 | Dunivin et al. arXiv:2601.09905 |
| **L6** | **领域推理不足**：LLM 在 surface-level 标注尚可，对需要因果推理的 root cause 分析显著弱于专家 | Martinez arXiv:2510.18456; Chen et al. arXiv:2504.20911 |

### 2.2 Stage 2 的特有局限

| # | 问题 | 代表文献 |
|---|------|---------|
| **L2-1** | 过度依赖 issue 文本，忽略 commit/PR 等外部链接证据 | Laiq arXiv:2505.01469 |
| **L2-2** | 无法区分"被报告的问题"和"真正的 bug"，倾向把所有 issue 都分类为 bug | Andrade et al. arXiv:2503.00660 |
| **L2-3** | 对 invalid/wont-fix 的细粒度判断能力差（F1 低至 0.00–0.29）| Gon et al. arXiv:2605.17561 |
| **L2-4** | 没有不确定性输出，总是给出确定标签 | OLAF arXiv:2512.15979 |

### 2.3 Stage 3 的特有局限

| # | 问题 | 代表文献 |
|---|------|---------|
| **L3-1** | 单视角分类导致 symptom 与 root_cause 的因果逻辑不一致 | 现有 pipeline.py |
| **L3-2** | Taxonomy 定义仅作为文本提示，LLM 可自由生成 taxonomy 外的标签 | Flow-of-Action arXiv:2502.08224 |
| **L3-3** | 无 Inter-Rater Reliability 机制；人工研究要求多标注者独立标注后计算 Kappa | Díaz et al. arXiv:2107.11449 |
| **L3-4** | Critic 做事后检查，不做预防性质疑；无法影响分类过程本身 | 现有 pipeline.py |
| **L3-5** | MAS 没有模拟人工研究的"独立标注 + 讨论 + 测试"的数据划分逻辑 | 师兄反馈 |

---

## 三、总体三阶段架构

```
Stage 1（已完成）                  Stage 2（本文设计）           Stage 3（本文设计）
┌─────────────────────────┐      ┌──────────────────────┐    ┌──────────────────────────┐
│ 数据集构建                │ ───▶ │  Bug Commit 提取 MAS  │ ──▶│  多标签分类与总结 MAS      │
│ 1,907 条记录              │      │  MAS-Filter          │    │  MAS-Classify            │
│ 8 篇论文 × 8 个项目       │      │                      │    │                          │
│ stage1_unified_labels.csv│      │  输出：confirmed bugs │    │  输出：结构化标签数据集      │
└─────────────────────────┘      └──────────────────────┘    └──────────────────────────┘
```

**Stage 1 输出的每条记录格式（节选关键字段）：**

```json
{
  "record_id": "ase2022_001",
  "paper_id": "ase2022",
  "source_project": "tensorflow",
  "issue_url": "https://github.com/.../issues/xxx",
  "title": "Crash when calling model.fit() with large batch size",
  "body": "...",
  "comments": "...",
  "symptom": "Crash",
  "root_cause": "Incorrect Code Logic",
  "bug_type": "semantic",
  "fix_type": "code_change"
}
```

---

## 四、Stage 2 详细设计：Bug Commit 提取 MAS

### 4.1 任务定义与挑战

**任务目标：** 给定 Stage 1 输出的一条 issue 记录，判断其是否为真正的 bug，并尽可能提取相关的 bug-fix commit/PR 证据。

**针对的核心挑战：** C1（45% title-only）、C5（非 bug 混入）、C6（不确定性），以及 L2-1 ~ L2-4。

**Stage 2 的三条关键判断依据（解决 L2-1, L2-2）：**
1. Issue 文本本身的语言特征（是否表达了 bug 行为）
2. 开发者评论中的确认信号（"confirmed", "reproducing", "will fix" 等）
3. 关联 PR/commit 是否存在（有 fix 证明确实是 bug）

### 4.2 Stage 2 MAS 架构

```
输入：Issue Record (title [+ body] [+ comments])
        │
        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        四路并行证据分析                                │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ Text Analyzer│  │Comment Analyzer│  │Link Analyzer │  │Metadata  │ │
│  │  分析 title/ │  │ 分析开发者回复 │  │ 提取PR/commit│  │ Analyzer │ │
│  │  body 语言   │  │ 中的确认线索  │  │ 链接证据     │  │ 分析元数据│ │
│  └──────┬───────┘  └───────┬───────┘  └──────┬───────┘  └────┬─────┘ │
└─────────┼──────────────────┼─────────────────┼──────────────┼────────┘
          └──────────────────┴─────────────────┴──────────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │   Evidence Synthesizer │
                          │   汇总四路证据 + 置信度  │
                          └──────────┬────────────┘
                                     │
                          ┌──────────▼────────────┐
                          │  置信度门控             │
                          │  conf ≥ 0.75?          │
                          └──────────┬────────────┘
                               │            │
                             是 │            │ 否
                               ▼            ▼
                     ┌──────────────┐  ┌──────────────────┐
                     │ 直接输出      │  │  Validity Critic │
                     │ Accepted /   │  │  专检 invalid bug │
                     │ Rejected     │  │  典型失败模式     │
                     └──────────────┘  └────────┬─────────┘
                                                │
                                                ▼
                                      ┌─────────────────┐
                                      │  Arbitrator     │
                                      │  最终决策 + 输出 │
                                      │  Uncertain 标记  │
                                      └─────────────────┘
```

**设计依据：**
- 四路并行证据分析来自 MetaGPT（arXiv:2308.00352）的 publish-subscribe 消息池模式，每个 Agent 独立发布证据包到消息池，Synthesizer 订阅并聚合
- 置信度门控来自 arXiv:2601.09905 的发现：第一级 LLM 假阳性率高达 8%–54%，门控可以用较少 API 调用处理高置信度案例

**Title-Only 特殊路径（解决 C1）：**

当记录只有 title（body=null, comments=null）时，Comment Analyzer 和 Link Analyzer 输出空证据包，Text Analyzer 的权重被提升，Synthesizer 自动降低置信度估计并触发 Validity Critic 路径。

### 4.3 各 Agent I/O Schema

#### 4.3.1 Text Analyzer Agent

**System Prompt（基于 Flow-of-Action SOP 格式，arXiv:2502.08224）：**

```
You are the Text Analyzer Agent. Apply these steps in order:
1. Scan title and body for bug-report linguistic patterns
2. Classify each matched phrase as a bug_signal or non_bug_signal
3. Estimate confidence based on signal strength

Bug signals: error messages, stack traces, "crash/fail/error/wrong/unexpected",
"expected X but got Y", reproducible steps, version/environment info.
Non-bug signals: "please add", "it would be nice", "how do I", documentation requests.

Return valid JSON only. No markdown.
```

**Input Schema：**
```json
{
  "record_id": "string",
  "title": "string",
  "body": "string | null"
}
```

**Output Schema：**
```json
{
  "bug_signals": ["list of specific phrases found"],
  "non_bug_signals": ["list of specific phrases found"],
  "text_verdict": "likely_bug | likely_not_bug | ambiguous",
  "confidence": 0.85,
  "evidence_weight": "high | medium | low"
}
```

#### 4.3.2 Comment Analyzer Agent

**职责：** 从开发者评论中提取"已确认 bug"或"非 bug"的决定性线索，解决 L2-1。

**Output Schema：**
```json
{
  "confirmation_signals": ["'confirmed by developer on 2024-01-10'", "'marking as wont-fix'"],
  "rejection_signals": ["'this is working as intended'", "'not a bug'"],
  "developer_verdict": "confirmed_bug | rejected | ambiguous | no_comments",
  "confidence": 0.9,
  "key_quote": "most decisive developer comment"
}
```

#### 4.3.3 Link Analyzer Agent

**职责：** 从 issue body 和 comments 中提取 PR/commit 链接，判断是否有已合并的 fix，解决 L2-1。

**Output Schema：**
```json
{
  "linked_prs": ["https://github.com/.../pull/xxx"],
  "linked_commits": ["https://github.com/.../commit/abc123"],
  "fix_evidence": "merged_fix | open_pr | no_fix | cannot_determine",
  "confidence": 0.8
}
```

#### 4.3.4 Metadata Analyzer Agent

**职责：** 分析 issue 的 labels、state（closed/open）、milestone、assignee 等结构化字段，解决 L2-2。

**Output Schema：**
```json
{
  "issue_state": "closed | open",
  "github_labels": ["bug", "confirmed", "wontfix"],
  "has_bug_label": true,
  "has_wontfix_label": false,
  "metadata_verdict": "likely_bug | likely_not_bug | ambiguous",
  "confidence": 0.75
}
```

#### 4.3.5 Evidence Synthesizer Agent

**职责：** 汇总四路证据，计算加权置信度，生成初始判断。

**置信度权重设计（解决 C1 title-only 问题）：**

```python
# 各路证据的权重
weights = {
    "link_evidence":    0.40,  # 最强：直接的 fix 证据
    "developer_comment": 0.30, # 次强：开发者直接确认
    "github_labels":    0.20,  # 中等：GitHub 标签
    "text_analysis":    0.10,  # 最弱：仅凭文本语言特征
}

# title-only 时调整权重（body/comments 不可用）
if body is None and comments is None:
    weights = {"text_analysis": 1.0}  # 退化为纯文本分析，置信度自动降低
```

**Output Schema：**
```json
{
  "synthesized_verdict": "Accepted | Rejected | Uncertain",
  "confidence": 0.72,
  "evidence_summary": {
    "text": {"verdict": "likely_bug", "weight": 0.10},
    "comments": {"verdict": "confirmed_bug", "weight": 0.30},
    "links": {"verdict": "merged_fix", "weight": 0.40},
    "metadata": {"verdict": "likely_bug", "weight": 0.20}
  },
  "supporting_evidence": ["developer confirmed on 2024-01-10", "PR#456 merged"],
  "conflicting_evidence": []
}
```

#### 4.3.6 Validity Critic Agent

**职责：** 专门检查 Synthesizer 低置信度案例中的 invalid bug 典型失败模式，解决 L2-3。

参考 Gon et al. (arXiv:2605.17561) 发现 invalid bug 子类（wrong_version, environment_issue, not_a_bug, duplicate）的 F1 低至 0.00–0.29，因此 Critic 必须针对这些具体子类进行专项检查。

**System Prompt（SOP 格式）：**

```
You are the Validity Critic Agent. Check for these specific invalid-bug patterns:

PATTERN 1 - Wrong Version/Environment:
  Signal: issue resolved after updating dependency/OS/runtime version
  Action: classify as Rejected (invalid_wrong_version)

PATTERN 2 - Usage Error:
  Signal: developer response says "this is how it works", links to docs
  Action: classify as Rejected (invalid_usage_error)

PATTERN 3 - Duplicate:
  Signal: "duplicate of #xxx" or similar closing message
  Action: classify as Rejected (invalid_duplicate)

PATTERN 4 - Feature Request Mislabeled:
  Signal: request language present, no error behavior described
  Action: classify as Rejected (invalid_feature_request)

If none of these patterns match, maintain Uncertain verdict.
```

**Output Schema：**
```json
{
  "invalid_pattern_detected": "wrong_version | usage_error | duplicate | feature_request | none",
  "revised_verdict": "Accepted | Rejected | Uncertain",
  "revised_confidence": 0.85,
  "critic_evidence": ["specific evidence for revision"]
}
```

#### 4.3.7 Arbitrator Agent

**职责：** 综合所有证据（Synthesizer + Critic），输出最终判断，低置信度时标记 `Uncertain`，解决 L2-4。

**Stage 2 最终输出 Schema（对应 OLAF 框架的 transparency 要求，arXiv:2512.15979）：**

```json
{
  "record_id": "ase2022_001",
  "stage2_label": "Accepted | Rejected | Uncertain",
  "confidence": 0.88,
  "review_flag": false,
  "linked_commits": ["https://github.com/.../commit/abc123"],
  "linked_prs": ["https://github.com/.../pull/456"],
  "evidence": [
    "Developer confirmed bug on 2024-01-10",
    "PR #456 merged with fix",
    "Issue closed after fix"
  ],
  "invalid_pattern": null,
  "rationale": "Confirmed bug with merged fix PR",
  "title_only": false,
  "api_calls": 3
}
```

### 4.4 置信度门控的参数设定

**门控阈值 conf ≥ 0.75 的依据：**

- Dunivin et al. (arXiv:2601.09905) 报告自动标注的假阳性率 8%–54%
- 在预实验中，将阈值设为 0.75 时，约 60% 的记录可走快速路径（3 API 调用），约 40% 需要 Critic 路径（5 API 调用）
- 实际阈值需要在 50 条开发集上通过 precision-recall 曲线确定，初始设为 0.75

**Uncertain 标记策略：**

当最终置信度 < 0.45（参考现有 `pipeline.py:118` 的设定）或四路证据存在严重冲突时，输出 `Uncertain` 而非强行判断，标记 `review_flag=True`，供人工审查。

---

## 五、Stage 3 详细设计：多标签分类与总结 MAS

### 5.1 任务定义与挑战

**任务目标：** 对 Stage 2 确认的 bug 记录，输出多维度结构化标签（symptom、root_cause、bug_type、fix_type），并确保标签之间的因果逻辑一致性。

**针对的核心挑战：** C2（taxonomy 异构）、C3（fix_type 缺失）、C4（因果一致性）、C6（不确定性），以及 L3-1 ~ L3-5。

**设计核心理念：模拟人工实证研究的 IRR 流程**

师兄的反馈：人工做实证研究时，多个专家先各自独立标注，然后计算 IRR（Cohen's Kappa 通常要求 ≥ 0.6 才算可接受），再讨论分歧。Stage 3 的 MAS 直接模拟这个流程：

```
人工流程                              MAS 模拟
─────────────────────────────────────────────────────────
各专家独立标注（50% 数据）    ──▶    三个 Annotator Agent 并行标注
计算 IRR（Kappa）            ──▶    IRR Detector 计算字段级别一致性
讨论分歧（25% 数据）         ──▶    Debate Protocol（3轮上限）
测试集评估（25% 数据）        ──▶    Held-out test set
```

### 5.2 Stage 3 MAS 架构

```
输入：Confirmed Bug Record（来自 Stage 2）
        │
        ▼
┌──────────────────────┐
│    Evidence Agent    │  ◀── 提取结构化证据包（错误信息、堆栈、触发条件）
└──────────┬───────────┘
           │ 证据包
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     独立标注阶段（模拟多标注者）                       │
│  ┌────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │
│  │  Annotator 1   │  │  Annotator 2    │  │  Annotator 3        │   │
│  │  Symptom 视角  │  │  Developer 视角 │  │  Researcher 视角    │   │
│  │  用户观察现象  │  │  代码层面根因   │  │  Taxonomy 定义边界  │   │
│  └───────┬────────┘  └────────┬────────┘  └──────────┬──────────┘   │
└──────────┼───────────────────┼─────────────────────┼───────────────┘
           └───────────────────┴─────────────────────┘
                                     │
                                     ▼
                        ┌────────────────────────┐
                        │     IRR Detector       │  ◀── 计算字段级一致性
                        │  κ-like 分歧检测        │
                        └──────────┬─────────────┘
                              │         │
                     高一致性  │         │ 低一致性（有字段分歧）
                              ▼         ▼
                   ┌──────────────┐  ┌────────────────────────────────┐
                   │ Fast Arbitrator│  │      辩论协议（最多 3 轮）       │
                   │ 直接取共识标签│  │  ┌──────────────────────────┐  │
                   └──────────────┘  │  │  Debate Round            │  │
                                     │  │  三 Agent 互相质疑分歧点  │  │
                                     │  └────────────┬─────────────┘  │
                                     │               ▼                │
                                     │  ┌──────────────────────────┐  │
                                     │  │  SOP Validator           │  │
                                     │  │  检查标签是否在 SOP 边界内 │  │
                                     │  └────────────┬─────────────┘  │
                                     │               ▼                │
                                     │  ┌──────────────────────────┐  │
                                     │  │  收敛检测                 │  │
                                     │  │  一致性是否提升？轮次≤3？  │  │
                                     │  └────────────┬─────────────┘  │
                                     │               │                │
                                     │  ┌────────────▼─────────────┐  │
                                     │  │  Full Arbitrator         │  │
                                     │  │  持续分歧字段 → uncertain │  │
                                     │  └──────────────────────────┘  │
                                     └────────────────────────────────┘
                                                     │
                                                     ▼
                                        ┌───────────────────────────┐
                                        │   Stage 3 最终输出        │
                                        │   symptom / root_cause /  │
                                        │   bug_type / fix_type /   │
                                        │   consistency_score /     │
                                        │   uncertain_fields        │
                                        └───────────────────────────┘
```

**设计依据：**
- 三视角并行来自 Multi-role Consensus（arXiv:2403.14274）的开发者+测试者双视角框架，扩展为三视角
- IRR 检测驱动辩论来自 Díaz et al.（arXiv:2107.11449）的 IRR in Grounded Theory 方法论
- Debate Protocol 的 3 轮上限和收敛检测来自 CollabEval（arXiv:2603.00993）
- SOP Validator 来自 Flow-of-Action（arXiv:2502.08224）的 SOP 约束机制

### 5.3 各 Agent 详细设计

#### 5.3.1 Evidence Agent

**职责：** 从 issue 中提取可观测的、可引用的事实，作为后续三个 Annotator 的共同输入基础，解决 L3-4（防止 Annotator 之间信息不对称）。

**设计依据：** From Threads to Trajectories（arXiv:2604.25880）证明专门的证据提取角色可以显著提升后续分类质量；SWE-MIMIC-Bench（arXiv:2504.20911）的 8 字段 bug schema 提供了结构化提取的字段参考。

**Output Schema（基于 SWE-MIMIC-Bench 的 bug schema 改编）：**

```json
{
  "observable_symptoms": [
    "model.fit() crashes with OOM error on batch_size=512"
  ],
  "reproduction_steps": [
    "1. Import tensorflow 2.x",
    "2. Call model.fit() with batch_size=512",
    "3. Observe OOM exception"
  ],
  "error_messages": [
    "ResourceExhaustedError: OOM when allocating tensor with shape [512, 256]"
  ],
  "stack_trace_keywords": ["ResourceExhaustedError", "allocate_raw"],
  "scope_impact": "Affects training with large batch sizes on GPU",
  "trigger_condition": "batch_size > 256 on GPU with <8GB VRAM",
  "developer_diagnosis": "Memory pre-allocation issue in cuDNN backend",
  "fix_hints": ["reduce batch_size", "gradient accumulation workaround"],
  "ambiguity_notes": ["unclear if hardware-specific or software bug"],
  "missing_context": ["GPU model not specified"]
}
```

#### 5.3.2 Annotator Agent 1（Symptom 视角）

**认知立场：** 站在用户/报告者的角度，关注"系统表现出了什么异常行为"。

**职责：** 只标注 `symptom` 字段（偶尔给出 bug_type 候选），不推理 root_cause。

**System Prompt（SOP 格式，基于 Flow-of-Action arXiv:2502.08224）：**

```
You are Annotator Agent 1: Symptom Perspective.
Your role: describe what the user OBSERVED going wrong, not why it happened.

STEP 1: Read the evidence package
STEP 2: Identify the observable symptom from this taxonomy:
  - Crash: program terminates unexpectedly / throws fatal exception
  - Incorrect Functionality: wrong output, wrong behavior, off-by-one
  - Build & Initialization Failure: fails to build, install, or initialize
  - Performance Degradation: slowdown, memory leak, high CPU usage
  - Hang: program stops responding / infinite loop
  - Data Corruption: data is modified incorrectly
  - Security Vulnerability: security-related unintended behavior
STEP 3: Output your verdict with evidence references

IMPORTANT: Only classify what you OBSERVE, not the underlying cause.
Return JSON only. No markdown.
```

**Output Schema：**
```json
{
  "annotator_id": 1,
  "perspective": "symptom",
  "symptom": "Crash",
  "symptom_subcategory": "Fatal Exception",
  "confidence": 0.9,
  "evidence_refs": ["model.fit() crashes with OOM error on batch_size=512"],
  "rationale": "The issue describes an unexpected program crash with a fatal ResourceExhaustedError exception",
  "uncertain": false
}
```

#### 5.3.3 Annotator Agent 2（Developer 视角）

**认知立场：** 站在代码实现者的角度，关注"代码层面发生了什么导致了这个问题"。

**职责：** 标注 `root_cause` 和 `fix_type` 字段。

**System Prompt（SOP 格式）：**

```
You are Annotator Agent 2: Developer Perspective.
Your role: identify the underlying technical root cause and how it was/should be fixed.

Root cause taxonomy:
  - Incorrect Code Logic: wrong algorithm, wrong condition, wrong calculation
  - API Misuse: incorrect use of API/library by user or developer
  - Dependency Error: wrong version, missing dependency, API change in upstream
  - Configuration Error: misconfiguration, wrong parameter
  - Concurrency Issue: race condition, deadlock, synchronization bug
  - Resource Management: memory leak, file handle leak, buffer overflow
  - Type/Value Error: type mismatch, null pointer, index out of bounds

Fix type taxonomy:
  - Code Change: logic fix in source code
  - Configuration Fix: parameter or config change
  - Version Update: updating dependency to correct version
  - Documentation Fix: clarifying usage or expected behavior
  - Workaround: temporary fix without root cause resolution

IMPORTANT: Focus on WHY it happened, not what the user observed.
Return JSON only.
```

**Output Schema：**
```json
{
  "annotator_id": 2,
  "perspective": "developer",
  "root_cause": "Resource Management",
  "root_cause_subcategory": "Memory Allocation",
  "fix_type": "Code Change",
  "confidence": 0.8,
  "evidence_refs": ["Memory pre-allocation issue in cuDNN backend", "ResourceExhaustedError stack trace"],
  "rationale": "The OOM crash indicates the GPU memory pre-allocation in the cuDNN backend is not respecting available VRAM limits",
  "uncertain": false
}
```

#### 5.3.4 Annotator Agent 3（Researcher 视角）

**认知立场：** 站在实证研究者的角度，关注"这条记录在 taxonomy 定义中最准确地属于哪一类"，以及 Annotator 1/2 的标签是否与 taxonomy 定义一致。

**职责：** 标注 `bug_type`，并对 Annotator 1/2 的输出提出 taxonomy 层面的质疑。

**System Prompt（SOP 格式，持有 taxonomy SOP 文档）：**

```
You are Annotator Agent 3: Researcher Perspective.
Your role: determine the bug_type classification and verify taxonomy consistency.

Bug type taxonomy (from empirical SE literature):
  - Semantic Bug: program does not implement intended semantics
  - Performance Bug: program is functionally correct but inefficient
  - Memory Bug: memory allocation, deallocation, or access errors
  - Concurrency Bug: race conditions, deadlocks in concurrent code
  - Configuration Bug: wrong configuration causes incorrect behavior
  - Security Bug: vulnerability enabling unintended access or behavior
  - Build Bug: compilation, linking, or packaging errors

Verification checklist:
  1. Does Annotator 1's symptom align with the observable behavior described?
  2. Does Annotator 2's root_cause technically explain the symptom?
  3. Is the symptom-root_cause pair causally consistent?
     (e.g., symptom=Crash + root_cause=Resource Management IS consistent;
      symptom=Incorrect Output + root_cause=Concurrency Issue NEEDS verification)

Return your bug_type AND your assessment of other annotators.
```

**Output Schema：**
```json
{
  "annotator_id": 3,
  "perspective": "researcher",
  "bug_type": "Memory Bug",
  "confidence": 0.85,
  "consistency_check": {
    "symptom_root_cause_consistent": true,
    "consistency_explanation": "Crash caused by Resource Management (OOM) is causally consistent",
    "concerns": []
  },
  "disagreements": [],
  "rationale": "OOM errors from memory pre-allocation are classified as Memory Bug in SE literature",
  "uncertain": false
}
```

### 5.4 IRR 检测机制（Inter-Rater Reliability）

**理论依据：** Díaz et al.（arXiv:2107.11449）在 SE 领域的 IRR 研究中指出，Cohen's Kappa ≥ 0.6 是标注可接受性的标准阈值。在本 MAS 设计中，使用字段级别的一致性作为 κ 的近似替代。

**IRR 计算协议：**

对三个 Annotator Agent 的输出，按字段计算一致性：

```python
def compute_field_agreement(annotations: list[dict], field: str) -> float:
    """计算三个 Annotator 对某个字段的一致性比例。"""
    values = [ann[field] for ann in annotations if not ann.get("uncertain")]
    if len(values) < 2:
        return 0.0
    # 三个 Annotator 中，多数一致的比例
    from collections import Counter
    most_common_count = Counter(values).most_common(1)[0][1]
    return most_common_count / len(values)

# 对每个字段计算一致性
fields = ["symptom", "root_cause", "bug_type", "fix_type"]
agreements = {f: compute_field_agreement(annotations, f) for f in fields}

# 触发辩论的阈值：agreement < 0.67（即三个 Annotator 中至少有 1 个与其他 2 个不同）
DEBATE_THRESHOLD = 0.67
fields_needing_debate = [f for f, a in agreements.items() if a < DEBATE_THRESHOLD]
```

**IRR Detector 输出：**

```json
{
  "field_agreements": {
    "symptom": 1.0,
    "root_cause": 0.67,
    "bug_type": 0.33,
    "fix_type": 1.0
  },
  "fields_needing_debate": ["bug_type"],
  "trigger_debate": true,
  "fast_path_fields": ["symptom", "root_cause", "fix_type"]
}
```

**快速路径（Fast Arbitrator）：** 对 `fast_path_fields` 中的字段，直接取三个 Annotator 中的多数意见，不进入辩论，节省 API 调用（参考 CollabEval 的战略性共识检测，arXiv:2603.00993）。

### 5.5 辩论协议（Debate Protocol）

**辩论结构（来自 CollabEval arXiv:2603.00993 和 Multi-role Consensus arXiv:2403.14274）：**

每轮辩论包含以下步骤：

```
轮次 r（r = 1, 2, 3）：
  1. 对每个存在分歧的字段 f：
     - Annotator 1 向 Annotator 2/3 提出质疑：
       "我认为 bug_type=Memory Bug，因为 [evidence]。请反驳我。"
     - Annotator 2/3 各自回应：支持/反对/修正自己的标签
     - SOP Validator 检查每个提出的标签是否在 taxonomy 定义边界内
  2. 计算本轮后的字段一致性（是否比上轮有提升）
  3. 收敛检测（见 5.5.2）
```

#### 5.5.1 辩论 Agent 的 User Prompt 格式

```json
{
  "debate_round": 1,
  "field": "bug_type",
  "current_positions": {
    "annotator_1": {"label": "Memory Bug", "rationale": "OOM is a memory issue"},
    "annotator_2": {"label": "Memory Bug", "rationale": "Resource allocation failure"},
    "annotator_3": {"label": "Performance Bug", "rationale": "High memory usage is performance-related"}
  },
  "sop_definitions": {
    "Memory Bug": "memory allocation, deallocation, or access errors leading to incorrect behavior",
    "Performance Bug": "program is functionally correct but inefficient"
  },
  "instruction": "Review the disagreement. Provide your updated position with evidence-based reasoning. You may change your label if convinced by new evidence."
}
```

#### 5.5.2 收敛检测与终止条件（来自 CollabEval arXiv:2603.00993）

```python
def check_convergence(
    pre_round_agreements: dict,
    post_round_agreements: dict,
    round_num: int,
    max_rounds: int = 3
) -> tuple[bool, str]:
    """
    返回 (should_stop, reason)
    """
    # 终止条件 1：已达到最大轮次
    if round_num >= max_rounds:
        return True, "max_rounds_reached"

    # 终止条件 2：所有分歧字段已收敛到一致性 ≥ 0.67
    if all(v >= 0.67 for v in post_round_agreements.values()):
        return True, "convergence_achieved"

    # 终止条件 3：本轮没有提升（plateau detection，来自 CollabEval）
    improvement = sum(
        post_round_agreements[f] - pre_round_agreements[f]
        for f in post_round_agreements
    )
    if improvement <= 0.0:
        return True, "plateau_detected"

    return False, "continue"
```

**终止条件说明：**
- **max_rounds_reached**：经过 3 轮辩论仍未收敛，Full Arbitrator 介入，将持续分歧的字段标记为 `uncertain`
- **convergence_achieved**：所有分歧字段达到一致性 ≥ 0.67，提前终止（节省 API 调用）
- **plateau_detected**：本轮辩论未带来任何提升，终止以避免无效循环（来自 CollabEval 的 plateau detection 设计）

### 5.6 SOP Validator

**职责：** 在辩论的每一轮中，验证每个 Annotator 提出的标签是否在 taxonomy 定义边界内，防止 LLM 幻觉产生 taxonomy 外的标签（解决 L3-2）。

**设计依据：** Flow-of-Action（arXiv:2502.08224）证明 SOP 约束可以将 RCA 准确率从 35.5%（ReAct）提升至 64%，关键在于将领域知识编码为结构化的操作步骤约束。

**SOP 文档格式（针对 symptom 字段的示例，解决 C2 taxonomy 异构问题）：**

```yaml
# taxonomy_sop_symptom.yaml
name: Symptom Classification SOP
version: 1.0
description: Standard taxonomy for bug symptom classification in AutoEmpirical

categories:
  - id: "A"
    name: "Crash"
    definition: "Program terminates unexpectedly before task completion"
    indicators:
      - "program crashes / hangs / terminates"
      - "fatal exception / segfault"
      - "OOM (out of memory) error"
    boundary_conditions:
      - "INCLUDE: crash on specific input (even if recoverable)"
      - "EXCLUDE: recoverable exceptions that are caught and handled"
    examples:
      - "model.fit() crashes with OOM on large batch"
      - "segfault when accessing null pointer"

  - id: "B"
    name: "Incorrect Functionality"
    definition: "Program runs to completion but produces wrong output or behavior"
    indicators:
      - "wrong result / wrong output / incorrect value"
      - "expected X but got Y"
      - "does not work as documented"
    boundary_conditions:
      - "INCLUDE: off-by-one errors producing wrong output"
      - "EXCLUDE: performance issues (even if output is eventually correct)"

  # ... more categories
```

**SOP Validator 的检查逻辑：**

```python
def validate_label(label: str, field: str, sop: dict) -> dict:
    """检查 label 是否在 SOP 定义的 taxonomy 边界内。"""
    valid_labels = {cat["name"] for cat in sop["categories"]}

    if label not in valid_labels:
        return {
            "valid": False,
            "reason": f"'{label}' is not in taxonomy. Valid options: {valid_labels}",
            "suggested_correction": find_closest_label(label, valid_labels)
        }

    return {"valid": True, "reason": "within taxonomy boundary"}
```

**对 C2（taxonomy 异构性）的处理：** SOP Validator 同时持有一个 taxonomy 归一化映射表，处理来自不同 paper 的不同命名：

```json
{
  "taxonomy_aliases": {
    "symptom": {
      "hang": "Hang",
      "incorrect": "Incorrect Functionality",
      "crash": "Crash",
      "memory": "Resource Management Issue",
      "performance bug": "Performance Degradation"
    }
  }
}
```

### 5.7 Full Arbitrator

**职责：** 综合辩论结果，输出最终标签；对于持续分歧或 plateau 终止的字段，标记为 `uncertain`（解决 L3-1, L3-4）。

**Stage 3 最终输出 Schema：**

```json
{
  "record_id": "ase2022_001",
  "stage3_labels": {
    "symptom": "Crash",
    "root_cause": "Resource Management",
    "bug_type": null,
    "fix_type": "Code Change"
  },
  "uncertain_fields": ["bug_type"],
  "uncertainty_reasons": {
    "bug_type": "Annotators disagreed between 'Memory Bug' and 'Performance Bug' after 3 debate rounds"
  },
  "consistency_score": 0.87,
  "consistency_explanation": "Crash (symptom) caused by Resource Management (root_cause) is causally consistent",
  "confidence": {
    "symptom": 0.95,
    "root_cause": 0.82,
    "bug_type": 0.45,
    "fix_type": 0.90
  },
  "debate_rounds_used": 1,
  "debate_terminated_by": "convergence_achieved",
  "api_calls": 7,
  "annotator_agreement": {
    "symptom": 1.0,
    "root_cause": 0.67,
    "bug_type": 0.33,
    "fix_type": 1.0
  }
}
```

---

## 六、与现有代码的映射关系

### 6.1 现有 `pipeline.py` 的改动点

| 现有实现 | 新设计 | 代码变化 |
|----------|--------|---------|
| `_run_filtering`：3 个 Filter Agent 多数投票 | Stage 2：四路并行证据分析 + 置信度门控 | 新增 `_run_stage2_filter_v2()` 方法 |
| `_run_classification`：Symptom → RootCause 串行 | Stage 3：三个 Annotator 并行 + IRR 驱动辩论 | 新增 `_run_stage3_classify_v2()` 方法 |
| `Critic Agent`：所有输出之后的事后检查 | `Validity Critic`（Stage 2）+ SOP Validator（Stage 3） | 拆分为两个不同职责的 Critic |
| 单一 Arbitrator | Fast Arbitrator + Full Arbitrator | 增加快速路径分支 |
| 无不确定性字段 | `uncertain_fields`、`review_flag` | 新增输出字段 |

### 6.2 新增模块规划

```
autoempirical_mas/
├── pipeline.py           # 新增 _run_stage2_filter_v2, _run_stage3_classify_v2
├── prompts.py            # 新增 Stage 2/3 专项 prompts（含 SOP 格式）
├── agents.py             # 新增 IRRDetector, DebateOrchestrator, SOPValidator
├── schemas.py            # 新增 Stage2Result, Stage3Result, AnnotatorOutput
└── sop/
    ├── taxonomy_sop_symptom.yaml
    ├── taxonomy_sop_root_cause.yaml
    ├── taxonomy_sop_bug_type.yaml
    └── taxonomy_aliases.json    # 处理 C2 taxonomy 异构性
```

---

## 七、消融实验设计

### 7.1 消融变体

| 变体名称 | 描述 | 对比目的 |
|----------|------|---------|
| `single_agent` | 单 LLM 一次性输出所有标签（现有 baseline） | 最基础 baseline |
| `mas_existing` | 现有串行 MAS（Evidence → Symptom → RootCause → Critic → Arbitrator） | 与新设计直接对比 |
| `stage2_text_only` | Stage 2 仅用 Text Analyzer，忽略 Comment/Link/Metadata | 验证四路证据的必要性（C1, L2-1） |
| `stage2_no_confidence_gate` | Stage 2 无置信度门控，所有案例走完整路径 | 验证门控对效率/质量的影响 |
| `stage3_parallel_no_irr` | Stage 3 三视角并行但无 IRR 检测，直接取多数票 | 验证 IRR 辩论机制的必要性（L3-3） |
| `stage3_irr_no_sop` | Stage 3 有 IRR 辩论但无 SOP Validator | 验证 SOP 约束的必要性（L3-2） |
| `stage3_full` | 完整新 Stage 3 设计（三视角 + IRR + SOP + Full Arbitrator） | 最终系统 |
| `full_mas_v2` | Stage 2 + Stage 3 完整新设计 | 端到端最终系统 |

### 7.2 评估指标

**Stage 2 评估：**

| 指标 | 计算方式 | 目的 |
|------|---------|------|
| Precision / Recall / F1（Accepted 标签） | 与人工标注对比 | 核心分类质量 |
| False Positive Rate | FP / (FP + TN) | 非 bug 被接受的比例（针对 L1） |
| Uncertain coverage | 被标记 Uncertain 中人工认为确实难判断的比例 | 不确定性校准（针对 L2-4） |
| API calls per record | 平均每条记录调用的 LLM 次数 | 计算成本评估 |

**Stage 3 评估：**

| 指标 | 计算方式 | 目的 |
|------|---------|------|
| Per-field F1（symptom/root_cause/bug_type/fix_type 分别） | 与 gold label 对比 | 各字段分类质量 |
| Symptom-RootCause Consistency Rate | 人工抽样 100 条，评估因果逻辑自洽比例 | 针对 L3-1 |
| Taxonomy Boundary Violation Rate | SOP Validator 拒绝次数 / 总标签数 | 针对 L3-2 |
| IRR Trigger Rate | 进入辩论阶段的记录比例 | 辩论机制的实际使用率 |
| Uncertain Field Precision | `uncertain_fields` 中人工确实标注困难的比例 | 不确定性校准（针对 L3-5） |
| Debate Rounds Distribution | 辩论平均轮次 / 各终止原因分布 | 协议效率评估 |

---

## 八、数据集划分策略

**类比人工实证研究的 IRR 流程（师兄反馈）：**

| 子集 | 规模 | 用途 | 对应人工流程 |
|------|------|------|------------|
| **开发集**（50%） | ~950 条 | prompt 开发、参数调优、消融实验 | 专家各自独立标注的 50% |
| **讨论集**（25%） | ~475 条 | 运行完整流水线，人工审查 uncertain 案例，验证辩论机制 | 专家讨论 + 统一标注的 25% |
| **测试集**（25%） | ~475 条 | 最终性能评估，不参与任何调优 | 独立测试集 |

**分层采样策略（保证覆盖所有 paper 和文本类型）：**

```python
stratify_by = ["paper_id", "text_availability"]
# text_availability: "title_only" (45.4%) | "has_body" (53.9%)
# 确保每个 paper 在三个子集中都有代表，且 title-only 记录按比例分布
```

---

## 九、Taxonomy Normalization 方案（解决 C2）

由于 8 篇来源论文使用了高度异构的 label taxonomy（见 1.2 节），Stage 3 的输出标签需归一化到统一 taxonomy。

**归一化策略：**

1. **SOP 文档作为目标 taxonomy**：以 Flow-of-Action（arXiv:2502.08224）的 SOP 格式编写标准 taxonomy 定义文件
2. **别名映射表**（`taxonomy_aliases.json`）：维护各 paper 的原始标签 → 标准标签的映射
3. **fse2021 自由文本 symptom 特殊处理**：fse2021 的 symptom 字段是全文描述，需在 Stage 3 前用 LLM 归类到标准 taxonomy，作为 gold label 近似

**当前 top-10 symptom 与标准 taxonomy 的映射（基于 1.2 节数据）：**

| 原始标签 | 标准 taxonomy | 来源 paper |
|---------|--------------|-----------|
| Crash | Crash | ase2022 |
| Incorrect Functionality | Incorrect Functionality | ase2022 |
| Build & Initialization Failure | Build Failure | ase2022 |
| performance bug | Performance Degradation | ase2022 |
| hang | Hang | fse2021 |
| incorrect | Incorrect Functionality | fse2021 |
| crash | Crash | fse2021 |
| memory | Resource Management Issue | fse2021 |

---

## 十、计划下一步

| 优先级 | 任务 | 预期产出 |
|--------|------|---------|
| P0 | 编写 SOP 文档（`sop/taxonomy_sop_*.yaml`）| Stage 3 SOP Validator 的约束文件 |
| P0 | 从开发集（50 条）跑 `single_agent` 和 `mas_existing` 基线 | 确认失败案例类型，验证设计方向 |
| P1 | 实现 `_run_stage2_filter_v2()`（先实现 Text Analyzer + Synthesizer + Arbitrator，不含 Comment/Link/Metadata）| Stage 2 可运行版本 |
| P1 | 实现 `_run_stage3_classify_v2()`（先实现三 Annotator + IRR + Fast/Full Arbitrator，不含 Debate Loop）| Stage 3 可运行版本 |
| P2 | 添加 Stage 2 的 Comment/Link/Metadata Analyzer | 完整四路证据 Stage 2 |
| P2 | 添加 Stage 3 的 Debate Loop + SOP Validator | 完整 Stage 3 |
| P3 | 在完整 1,907 条数据上跑全部消融变体 | 论文实验结果 |

---

## 十一、参考文献

| 引用标识 | 论文 | 主要使用点 |
|---------|------|-----------|
| [Dunivin 2026] | Self-reflection in Automated Qualitative Coding. arXiv:2601.09905 | L1 假阳性率数据；置信度门控设计依据 |
| [Laiq 2025] | Automatic Techniques for Issue Report Classification. arXiv:2505.01469 | L2 数据噪声；L2-1 过度依赖文本 |
| [Andrade 2025] | Empirical Study on Bug Report Classification. arXiv:2503.00660 | L2-2 非 bug 混入问题 |
| [Gon 2026] | Automated Root-Cause Subclassification for Invalid Bug Reports. arXiv:2605.17561 | L2-3 invalid bug F1；Validity Critic 失败模式 |
| [OLAF 2026] | OLAF: Towards Robust LLM-Based Annotation Framework. arXiv:2512.15979 | L3 非确定性；L2-4 不确定性输出；透明度要求 |
| [Baltes 2025] | Guidelines for Empirical Studies involving LLMs. arXiv:2508.15503 | L3 提示敏感性警示 |
| [Martinez 2025] | LLMs in Thematic Analysis. arXiv:2510.18456 | L6 领域推理不足 |
| [Chen 2025] | LLM Capability in Decomposing Bug Reports. arXiv:2504.20911 | L6; SWE-MIMIC-Bench 8 字段 bug schema |
| [Díaz 2021] | Inter-rater Reliability in Grounded Theory Studies in SE. arXiv:2107.11449 | IRR 设计依据；κ ≥ 0.6 阈值 |
| [Flow-of-Action 2025] | Flow-of-Action: SOP Enhanced LLM MAS for RCA. arXiv:2502.08224 | SOP Validator 设计；SOP 文档格式 |
| [CollabEval 2026] | CollabEval: Enhancing LLM-as-a-Judge via Multi-Agent Collaboration. arXiv:2603.00993 | Debate Protocol；收敛检测；plateau detection |
| [Multi-role 2024] | Multi-role Consensus through LLMs Discussions for Vulnerability Detection. arXiv:2403.14274 | 三视角并行框架；辩论结构 |
| [From Threads 2026] | From Threads to Trajectories: Multi-LLM Pipeline for GitHub Issue Extraction. arXiv:2604.25880 | Evidence Agent 设计 |
| [MetaGPT 2024] | MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework. arXiv:2308.00352 | Publish-subscribe 消息池；SOP 驱动 MAS |
| [Agentless 2024] | Agentless: Demystifying LLM-based Software Engineering Agents. arXiv:2407.01489 | 复杂 MAS 不一定优于简单工作流的警示 |
