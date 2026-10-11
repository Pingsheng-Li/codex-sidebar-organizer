# Sidebar Organizer 0.1.2

新增经过逐条读取验证的 Codex 云端记录分类，并修复云端路由主机与侧边栏内部保存标识不同导致的误判。

- `codex` / `durable` 记录须通过原生读取、唯一成员位置和身份一致性检查，才可归入“Codex 云端 · 聊天”。内部 `local` 前缀不再被当成创建设备证据。
- 新增 `capture-cloud`，绑定前后快照各自新取得的身份数据；缺少证据、标识冲突、来源不可用时保持原样。
- 云端分组按需创建、同名复用；置顶、项目归属及手工分组继续保留。
- 两轮实际运行均确认全部 20 条云端记录：新增分组 0、移动 0、排除项 0、核对错误 0。现有 6 个分组、23 个项目和 6 条置顶保持不变。
- 49 项自动测试通过；两个 ZIP 解压后验证云端取证、分类、核对和重复运行流程，并通过隔离环境安装检查。
- 新增可直接用于项目介绍的 [中文简介](https://github.com/VeraPyuyi/codex-sidebar-organizer/blob/main/docs/INTRODUCTION.zh-CN.md)。

云端执行来源不代表聊天由哪台电脑或浏览器创建。以上是可读取记录的元数据验证；完整历史、界面显示与折叠、跨设备同步仍按实际能力说明。

## 安装或升级

旧版插件用户先执行第一条命令移除本插件的旧市场注册；首次安装用户跳过第一条。随后新建桌面会话加载新版技能。

```sh
codex plugin marketplace remove sidebar-organizer-marketplace
codex plugin marketplace add VeraPyuyi/codex-sidebar-organizer --ref v0.1.2
codex plugin add sidebar-organizer@sidebar-organizer-marketplace
```

独立 skill 用户下载 `organize-sidebar-skill-0.1.2.zip`，备份并替换同名技能文件夹。`sidebar-organizer-plugin-0.1.2.zip` 为插件目录包；`SHA256SUMS.txt` 提供校验值。选择一种安装方式即可。

[中文说明](https://github.com/VeraPyuyi/codex-sidebar-organizer#readme) · [English](https://github.com/VeraPyuyi/codex-sidebar-organizer/blob/main/README.en.md) · [验证范围](https://github.com/VeraPyuyi/codex-sidebar-organizer/blob/main/docs/VALIDATION.md)
