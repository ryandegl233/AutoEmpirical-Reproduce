# Stage1 Visual Analysis Summary

本阶段统一数据集共包含 1907 条人工标注记录，来自 8 个 source project、8 篇论文。

root_cause 字段覆盖 1907/1907 条记录，symptom 字段覆盖 1869/1907 条记录。

数据量最大的来源是：tensorflow/tfjs（682）；federated_learning（395）；pytorch（194）；autopilot_uav（168）；webassembly_compilers（146）。

最高频 root cause 是：Incorrect Code Logic（159）；API Misuse（73）；Dependency Error（61）；Data/Model Inaccessibility（55）；Logic error（50）；Inconsistency（49）；Unimplemented Operator（46）；Incompatibilitty between 3rd-party DL Library and TF.js（42）。

最高频 symptom 是：Crash（616）；Incorrect Functionality（186）；Build & Initialization Failure（141）；performance bug（137）；Poor Performance（114）；Functional error（62）；Stack Trace?; Incorrect Result Output/ Ground Truth Known?（40）；Unknown（36）。

最高频 bug type 是：framework（378）；web application（180）；performance bug（137）；Third-party library（124）；Model building（46）；FL Configuration（46）；GitHub/Issue（45）；Data Preparation（44）。

最高频 component 是：Backend（180）；PySyft（129）；FATE（125）；Ardupilot（103）；API（102）；Pytorch（95）；Core（72）；PX4（65）。

联合分析建议优先查看：source_project × root_cause、root_cause × symptom、bug_type × root_cause 三组图，因为它们最能反映不同论文数据集之间的标签口径差异和跨来源共性。
