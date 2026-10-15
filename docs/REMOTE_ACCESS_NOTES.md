# 远程访问场景备忘

记录日期：2026-10-15。状态：后续设计参考，暂不实施，也不代表已验证支持。

## 先区分连接路径与执行位置

VPN、SSH 跳板解决如何到达目标机器；HPC 调度器决定计算资源分配和任务在哪里执行。
两者可以组合，但不应统一当作“需要 Slurm 支持”的问题。

| 场景 | 连接与执行方式 | 后续考虑 |
|---|---|---|
| 校园内个人或课题组的独立服务器 | 本机接入学校 VPN 后 SSH，或经过学校跳板机；Codex 可在服务器上运行，前提是它能访问所需模型服务 | 通常是稳定的 SSH 目标，未必有调度器；先验证现有 SSH 配置即可 |
| HPC 的 compute node 无外网，Codex 留在 login/development node | 在集群允许的节点运行 Codex，编辑共享文件、提交作业、读取日志；实际计算通过调度器在 compute node 执行 | 这种工作流可以较简单，无需让整理器把 Codex 会话搬进 compute node；确认节点使用规则及文件可见性 |
| 确实需要在 HPC compute node 内运行 Codex | 获得有效 allocation 后，通过集群允许的 SSH 或调度器启动；还需模型服务访问能力 | 才需要研究作业与节点发现、环境加载、到期处理和会话恢复；节点名可能每次变化 |

VPN 可用于访问独立服务器，也可用于访问集群入口。跳板机也不一定是 HPC login node。
不能仅凭私有 IP 或经由跳板访问，就推断目标是计算节点。

## 已明确的取舍

- compute node 无网时，优先考虑让 Codex 留在可联网且允许运行它的入口或开发节点，通过调度器执行计算任务；不预设必须增加复杂的 compute-node 接入。
- 学校内部的个人服务器应作为独立场景评估。它可能长期在线、没有作业分配或到期机制，只需要 VPN 或跳板连通。
- 本机连上 VPN、SSH 能到达目标，并不自动让目标机器获得访问模型服务的网络出口。
- 暂未决定实现 Slurm 集成。先确认实际工作流，再确定是否需要新功能。

## 当前实现与待确认项

CLI 调用系统 OpenSSH，并沿用 SSH 别名中的连接配置。VPN 路由由系统管理，
`ProxyJump` 可交由 OpenSSH 处理；本项目尚未完成 VPN 或多跳环境的实机验收。
当前没有 allocation 管理，且显式使用 `RemoteCommand=none`，不能依赖别名中的
`RemoteCommand srun ...` 自动把会话移到计算节点。

后续遇到具体环境时，先确认：

1. 目标是固定的独立服务器，还是由调度器临时分配的节点？
2. 本机需要 VPN、SSH 跳板，还是两者都需要？
3. Codex 本身必须运行在哪里？是否只需要把计算任务提交到其他节点？
4. Codex 所在节点能否访问所需模型服务？项目文件和会话存储在哪里可见？
5. 若涉及 allocation，集群允许哪种进入方式，资源何时到期？

若未来支持动态计算节点，再评估按稳定的集群/项目标识组织会话；当前分组仍按实际
SSH 端点和远端 Codex 主目录隔离，不应声称已实现跨节点分组或会话迁移。

参考：[CLI 现有能力](../plugins/sidebar-organizer/skills/organize-sidebar/references/cli.md)、
[OpenSSH ProxyJump](https://man.openbsd.org/ssh_config#ProxyJump)、
[Slurm srun](https://slurm.schedmd.com/srun.html)。
