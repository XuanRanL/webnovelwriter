# 文档中心

`docs/` 目录已按稳定分区整理，避免所有说明文档平铺在根下。

## 目录索引

### 架构

- [`architecture/overview.md`](./architecture/overview.md)：系统架构、核心理念、Agent 分工与主数据链
- [`architecture/current-system-diagnosis.md`](./architecture/current-system-diagnosis.md)：当前实现状态的系统级诊断，聚焦读写链、提交语义与事实层问题

### 使用指南

- [`guides/commands.md`](./guides/commands.md)：`/webnovel-*` 命令入口与常见用法
- [`guides/rag-and-config.md`](./guides/rag-and-config.md)：RAG 检索链路、环境变量与配置优先级
- [`guides/genres.md`](./guides/genres.md)：题材模板与复合题材规则说明

### 运维

- [`operations/operations.md`](./operations/operations.md)：项目目录、恢复、插件目录与运行期路径说明

### 记忆系统

- [`memory/long-term-memory-architecture-v2.md`](./memory/long-term-memory-architecture-v2.md)：基于当前代码状态的长期记忆现有架构说明

### 研究与外部方案

- [`research/long-term-memory-research-report.md`](./research/long-term-memory-research-report.md)：长期记忆论文、基准与开源项目调研
- [`research/storyteller-paper-summary.md`](./research/storyteller-paper-summary.md)：`STORYTELLER` 论文总结

### Specs
- [`superpowers/README.md`](./superpowers/README.md)：当前架构 spec 与设计文档导航

## 分类原则

- `architecture/`：当前系统的稳定结构说明
- `guides/`：使用者需要直接查阅的命令、配置、题材说明
- `operations/`：运行、恢复、目录与部署相关手册
- `memory/`：当前已实现的长期记忆架构说明
- `research/`：论文总结与外部方案调研
- `superpowers/`：当前仍保留的架构 spec 与设计收敛文档

## 推荐阅读顺序

1. 先看 [`../README.md`](../README.md) 了解安装与基本使用。
2. 再看 [`architecture/overview.md`](./architecture/overview.md) 建立整体结构认知。
3. 需要配置检索时，看 [`guides/rag-and-config.md`](./guides/rag-and-config.md)。
4. 需要实际使用命令时，看 [`guides/commands.md`](./guides/commands.md)。
5. 需要排查运行问题时，看 [`operations/operations.md`](./operations/operations.md)。
