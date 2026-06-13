# 论文数据集三阶段数据总览

本文档按论文列出当前已纳入实验管道的 11 篇论文，每篇论文说明三组数据的数量与路径。

> **三阶段定义**
> - Stage 1 Raw：论文原始采集数据（直接来自论文 supplementary / GitHub，未经筛选）
> - Stage 2 Filtered：经过手工筛查后确认包含 bug label 的候选条目
> - Stage 3 Annotated：经过格式转换后的统一 schema 标注数据（`records.csv`）

---

## 汇总表

| # | paper_id | venue | year | 领域 | Stage1 Raw | Stage2 Filtered | Stage3 Annotated | Stage3 状态 |
|---|----------|-------|------|------|-----------|----------------|-----------------|------------|
| 1 | ase2020_cp_detector_using_configuration_related | ASE | 2020 | general_software | 173 | 173 | — | 待转换 |
| 2 | ase2021_an_empirical_study_of_bugs | ASE | 2021 | compiler | 1054 | 146 | **146** | ✅ 完成 |
| 3 | ase2022_towards_understanding_the_faults_of | ASE | 2022 | deep_learning_framework | 3859 | 684 | **699** | ✅ 完成 |
| 4 | fse2021_an_exploratory_study_of_autopilot | FSE | 2021 | iot_robotics | 569 | 168 | **168** | ✅ 完成 |
| 5 | fse2022_large_scale_analysis_of_non | FSE | 2022 | general_software | 3142 | 445 | — | 待转换 |
| 6 | fse2023_understanding_the_bug_characteristics_and | FSE | 2023 | general_software | 395 | 395 | **414** | ✅ 完成 |
| 7 | icpc2025_combining_language_and_app_ui | ICPC | 2025 | general_software | 75 | 54 | — | 待转换 |
| 8 | icse2022_an_empirical_study_on_performance | ICSE | 2022 | deep_learning_framework | 5578 | 141 | **143** | ✅ 完成 |
| 9 | icse2022_characterizing_and_detecting_bugs_in | ICSE | 2022 | web | 83 | 83 | **48** | ✅ 完成 |
| 10 | icse2023_an_empirical_study_on_bugs | ICSE | 2023 | deep_learning_framework | 2205 | 194 | **194** | ✅ 完成 |
| 11 | icse2024_understanding_transaction_bugs_in_database | ICSE | 2024 | database | 7775 | 140 | **140** | ✅ 完成 |

**当前已完成标注的论文：8 篇 / 11 篇，待转换：3 篇**

---

## 各论文详细信息

---

### 1. ase2020_cp_detector_using_configuration_related

| 字段 | 内容 |
|------|------|
| 论文题目 | CP-Detector: Using Configuration-related Performance Properties to Expose Performance Bugs |
| 领域 | general_software |
| 研究范围 | Configuration-related performance bugs |
| 数据来源 | GitHub Issues (Bug tracking systems) |
| 采集时间 | Before December 2020 |
| Stage 1 Raw 数量 | 173 |
| Stage 1 Raw 路径 | `data/raw/ase2020_cp_detector_using_configuration_related/` |
| Stage 2 Filtered 数量 | 173 |
| Stage 2 Filtered 路径 | `data/raw_stage1/ase2020_cp_detector_using_configuration_related/` |
| Stage 3 Annotated 数量 | — (待转换) |
| Stage 3 Annotated 路径 | `data/interim/stage1_converted/ase2020_cp_detector_using_configuration_related/records.csv` |
| 当前状态 | pending_raw_download_or_converter |
| 数据链接 | https://github.com/TimHe95/CP-Detector |

---

### 2. ase2021_an_empirical_study_of_bugs

| 字段 | 内容 |
|------|------|
| 论文题目 | An Empirical Study of Bugs in WebAssembly Compilers |
| 领域 | compiler |
| 研究范围 | WebAssembly compiler bugs |
| 数据来源 | GitHub Issues |
| 采集时间 | exclude bugs earlier than June 2015 |
| Stage 1 Raw 数量 | 1054 |
| Stage 1 Raw 路径 | `data/raw/ase2021_an_empirical_study_of_bugs/` |
| Stage 2 Filtered 数量 | 146 |
| Stage 2 Filtered 路径 | `data/raw_stage1/ase2021_an_empirical_study_of_bugs/` |
| Stage 3 Annotated 数量 | **146** |
| Stage 3 Annotated 路径 | `data/interim/stage1_converted/ase2021_an_empirical_study_of_bugs/records.csv` |
| 当前状态 | ✅ 完成 |
| 数据链接 | https://github.com/wasm-compiler-bugs/wasm-compiler-bugs.github.io/blob/master/Dataset/qualitative_dataset.csv |

**标注字段**：symptom, root_cause, bug_type, component, fix_type, trigger_condition, consequence, severity_or_impact

---

### 3. ase2022_towards_understanding_the_faults_of

| 字段 | 内容 |
|------|------|
| 论文题目 | Towards Understanding the Faults of JavaScript-Based Deep Learning Systems |
| 领域 | deep_learning_framework |
| 研究范围 | JavaScript DL Engines |
| 数据来源 | GitHub Issues |
| 采集时间 | before Dec. 2021 |
| Stage 1 Raw 数量 | 3859 |
| Stage 1 Raw 路径 | `data/raw/ase2022_towards_understanding_the_faults_of/` |
| Stage 2 Filtered 数量 | 684 |
| Stage 2 Filtered 路径 | `data/raw_stage1/ase2022_towards_understanding_the_faults_of/` |
| Stage 3 Annotated 数量 | **699** |
| Stage 3 Annotated 路径 | `data/interim/stage1_converted/ase2022_towards_understanding_the_faults_of/records.csv` |
| 当前状态 | ✅ 完成 |
| 数据链接 | https://docs.google.com/spreadsheets/d/18XDRZTSEYBVMveol1-rtNNUz8uiAsKgzvPxsKhssVYs |

**注意**：annotated(699) > filtered(684)，存在轻微数量差异，需检查转换器是否引入重复行

---

### 4. fse2021_an_exploratory_study_of_autopilot

| 字段 | 内容 |
|------|------|
| 论文题目 | An Exploratory Study of Autopilot Software Bugs in Unmanned Aerial Vehicles |
| 领域 | iot_robotics |
| 研究范围 | Unmanned aerial vehicles software bugs |
| 数据来源 | GitHub Issues |
| 采集时间 | Unknown |
| Stage 1 Raw 数量 | 569 |
| Stage 1 Raw 路径 | `data/raw/fse2021_an_exploratory_study_of_autopilot/` |
| Stage 2 Filtered 数量 | 168 |
| Stage 2 Filtered 路径 | `data/raw_stage1/fse2021_an_exploratory_study_of_autopilot/` |
| Stage 3 Annotated 数量 | **168** |
| Stage 3 Annotated 路径 | `data/interim/stage1_converted/fse2021_an_exploratory_study_of_autopilot/records.csv` |
| 当前状态 | ✅ 完成 |
| 数据链接 | https://doi.org/10.5281/zenodo.4898868 |

---

### 5. fse2022_large_scale_analysis_of_non

| 字段 | 内容 |
|------|------|
| 论文题目 | Large-Scale Analysis of Non-Termination Bugs in Real-World OSS Projects |
| 领域 | general_software |
| 研究范围 | Non-Termination Bugs |
| 数据来源 | GitHub Issues |
| 采集时间 | Before November 2022 |
| Stage 1 Raw 数量 | 3142 |
| Stage 1 Raw 路径 | `data/raw/fse2022_large_scale_analysis_of_non/` |
| Stage 2 Filtered 数量 | 445 |
| Stage 2 Filtered 路径 | `data/raw_stage1/fse2022_large_scale_analysis_of_non/` |
| Stage 3 Annotated 数量 | — (待转换) |
| Stage 3 Annotated 路径 | `data/interim/stage1_converted/fse2022_large_scale_analysis_of_non/records.csv` |
| 当前状态 | pending_raw_download_or_converter |
| 数据链接 | https://zenodo.org/records/6548310 |

---

### 6. fse2023_understanding_the_bug_characteristics_and

| 字段 | 内容 |
|------|------|
| 论文题目 | Understanding the Bug Characteristics and Fix Strategies of Federated Learning Systems |
| 领域 | general_software |
| 研究范围 | Federated Learning systems |
| 数据来源 | GitHub Issues |
| 采集时间 | before July 2022 |
| Stage 1 Raw 数量 | 395 |
| Stage 1 Raw 路径 | `data/raw/fse2023_understanding_the_bug_characteristics_and/` |
| Stage 2 Filtered 数量 | 395 |
| Stage 2 Filtered 路径 | `data/raw_stage1/fse2023_understanding_the_bug_characteristics_and/` |
| Stage 3 Annotated 数量 | **414** |
| Stage 3 Annotated 路径 | `data/interim/stage1_converted/fse2023_understanding_the_bug_characteristics_and/records.csv` |
| 当前状态 | ✅ 完成 |
| 数据链接 | https://github.com/CGCL-codes/FL_Bug_Study |

**注意**：annotated(414) > raw(395)，同样有少量差异，需检查是否有重复或来源文件包含额外条目

---

### 7. icpc2025_combining_language_and_app_ui

| 字段 | 内容 |
|------|------|
| 论文题目 | Combining Language and App UI Analysis for the Automated Assessment of Bug Reproduction Steps |
| 领域 | general_software |
| 研究范围 | Bug Reproduction Steps |
| 数据来源 | GitHub Issues |
| 采集时间 | Before 2024 |
| Stage 1 Raw 数量 | 75 |
| Stage 1 Raw 路径 | `data/raw/icpc2025_combining_language_and_app_ui/` |
| Stage 2 Filtered 数量 | 54 |
| Stage 2 Filtered 路径 | `data/raw_stage1/icpc2025_combining_language_and_app_ui/` |
| Stage 3 Annotated 数量 | — (待转换) |
| Stage 3 Annotated 路径 | `data/interim/stage1_converted/icpc2025_combining_language_and_app_ui/records.csv` |
| 当前状态 | pending_raw_download_or_converter |
| 数据链接 | https://github.com/sea-lab-wm/AstroBR-Bug-Reproduction-Steps-Assessment/blob/main/a_dataset/bug_reports/bug_reports.xlsx |

---

### 8. icse2022_an_empirical_study_on_performance

| 字段 | 内容 |
|------|------|
| 论文题目 | An Empirical Study on Performance Bugs in Deep Learning Frameworks |
| 领域 | deep_learning_framework |
| 研究范围 | Performance Bugs of TensorFlow and PyTorch |
| 数据来源 | GitHub Issues |
| 采集时间 | before February 2021 |
| Stage 1 Raw 数量 | 5578 |
| Stage 1 Raw 路径 | `data/raw/icse2022_an_empirical_study_on_performance/` |
| Stage 2 Filtered 数量 | 141 |
| Stage 2 Filtered 路径 | `data/raw_stage1/icse2022_an_empirical_study_on_performance/` |
| Stage 3 Annotated 数量 | **143** |
| Stage 3 Annotated 路径 | `data/interim/stage1_converted/icse2022_an_empirical_study_on_performance/records.csv` |
| 当前状态 | ✅ 完成 |
| 数据链接 | https://github.com/dlframeworkperfbugs/performance-bugs-in-dl-frameworks |

---

### 9. icse2022_characterizing_and_detecting_bugs_in

| 字段 | 内容 |
|------|------|
| 论文题目 | Characterizing and Detecting Bugs in WeChat Mini-Programs |
| 领域 | web |
| 研究范围 | WeChat Mini-Programs |
| 数据来源 | GitHub Issues |
| 采集时间 | Before May 2022 |
| Stage 1 Raw 数量 | 83 |
| Stage 1 Raw 路径 | `data/raw/icse2022_characterizing_and_detecting_bugs_in/` |
| Stage 2 Filtered 数量 | 83 |
| Stage 2 Filtered 路径 | `data/raw_stage1/icse2022_characterizing_and_detecting_bugs_in/` |
| Stage 3 Annotated 数量 | **48** |
| Stage 3 Annotated 路径 | `data/interim/stage1_converted/icse2022_characterizing_and_detecting_bugs_in/records.csv` |
| 当前状态 | ✅ 完成 |
| 数据链接 | https://github.com/tao2years/WeBug/blob/main/dataset/BugSet.xlsx |

**注意**：annotated(48) < filtered(83)，说明转换时过滤掉了约 35 条记录，需检查转换器逻辑是否正确

---

### 10. icse2023_an_empirical_study_on_bugs

| 字段 | 内容 |
|------|------|
| 论文题目 | An Empirical Study on Bugs Inside PyTorch: A Replication Study |
| 领域 | deep_learning_framework |
| 研究范围 | PyTorch Bugs |
| 数据来源 | GitHub Issues |
| 采集时间 | before 20 October 2022 |
| Stage 1 Raw 数量 | 2205 |
| Stage 1 Raw 路径 | `data/raw/icse2023_an_empirical_study_on_bugs/` |
| Stage 2 Filtered 数量 | 194 |
| Stage 2 Filtered 路径 | `data/raw_stage1/icse2023_an_empirical_study_on_bugs/` |
| Stage 3 Annotated 数量 | **194** |
| Stage 3 Annotated 路径 | `data/interim/stage1_converted/icse2023_an_empirical_study_on_bugs/records.csv` |
| 当前状态 | ✅ 完成 |
| 数据链接 | https://github.com/datasetsharing/pytorchbugdataset |

---

### 11. icse2024_understanding_transaction_bugs_in_database

| 字段 | 内容 |
|------|------|
| 论文题目 | Understanding Transaction Bugs in Database Systems |
| 领域 | database |
| 研究范围 | Transaction Bugs in Database Systems |
| 数据来源 | GitHub Issues |
| 采集时间 | January 2018 – December 2022 |
| Stage 1 Raw 数量 | 7775 |
| Stage 1 Raw 路径 | `data/raw/icse2024_understanding_transaction_bugs_in_database/` |
| Stage 2 Filtered 数量 | 140 |
| Stage 2 Filtered 路径 | `data/raw_stage1/icse2024_understanding_transaction_bugs_in_database/` |
| Stage 3 Annotated 数量 | **140** |
| Stage 3 Annotated 路径 | `data/interim/stage1_converted/icse2024_understanding_transaction_bugs_in_database/records.csv` |
| 当前状态 | ✅ 完成 |
| 数据链接 | https://github.com/tcse-iscas/TXBug/blob/main/TXBug%20Set.xlsx |

---

## 需要关注的问题

| 问题 | 涉及论文 | 说明 |
|------|---------|------|
| annotated > filtered | ase2022 (699>684), fse2023 (414>395), icse2022_perf (143>141) | 需确认转换器是否引入重复行或多来源文件 |
| annotated < filtered | icse2022_wechat (48<83) | 需确认转换器是否过度过滤，或原始数据中部分条目无法转换 |
| 未完成转换（Stage3 缺失） | ase2020, fse2022, icpc2025 | 需要实现对应的 converter 才能纳入 MAS 实验 |

---

*生成时间：2026-06-13*
