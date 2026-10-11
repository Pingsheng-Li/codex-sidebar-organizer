# Sidebar Organizer · 侧边栏整理

[English](README.en.md) · [下载 ZIP](https://github.com/VeraPyuyi/codex-sidebar-organizer/releases/latest) · [使用的 skill](plugins/sidebar-organizer/skills/organize-sidebar/SKILL.md)

在支持原生侧边栏工具的 Codex 桌面会话中，一句话按来源收纳项目和聊天。适合多台电脑、ChatGPT 云端项目和大量「最近」聊天混在一起的情况。

这是一个轻量技能插件：无需服务器、API Key 或额外 MCP 服务。**“自动归档”指分类收纳；不隐藏、删除或真正归档聊天。** 每次调用执行一轮，后续新增聊天可再次整理。

## 整理效果

```text
置顶                          ← 原有项目、聊天及顺序保留
▸ 本机 · 项目
▸ ChatGPT 云端 · 项目
▸ 本机 · 聊天
▸ ChatGPT 云端 · 聊天
▸ 远程 Workstation [host-a] · 项目   ← 有真实来源证据时增加
▸ 远程 Workstation [host-a] · 聊天
▸ 来源待确认
```

上图是布局示意，不表示自动折叠已完成。项目里的聊天继续留在项目下；原有手工分组保持原样。新分组使用原生折叠控件，是否能由助手收起取决于当前客户端提供的操作能力。

| 会做 | 处理方式 |
|---|---|
| 按实际来源分类 | 当前执行主机、已确认远程主机、ChatGPT 云端分别处理，不猜创建电脑 |
| 保留重要组织关系 | 保留置顶顺序、项目归属、文件路径和现有手工分组 |
| 重复运行 | 复用同名分区，只收纳尚未分类的条目 |
| 避免重复或错误移动 | 重名分区、未知身份、不可用来源跳过并报告 |
| 预览和核对 | 支持只预览；移动后回读元数据，报告失败和未验证项 |

## 快速安装：插件版

需要支持 `codex plugin` 命令的 Codex 版本。执行：

```sh
codex plugin marketplace add VeraPyuyi/codex-sidebar-organizer --ref v0.1.1
codex plugin add sidebar-organizer@sidebar-organizer-marketplace
```

重新打开一个 **Codex 桌面端会话**，选择 `organize-sidebar` 技能或输入：

```text
使用 $organize-sidebar，按来源整理我的项目和聊天，保留置顶和项目归属。
```

如果通过插件命名空间显示技能，选择 `sidebar-organizer:organize-sidebar`；也可以直接说「用 Sidebar Organizer 整理侧边栏」。CLI 用于安装，实际整理须在提供桌面侧边栏工具的会话里进行。没有这些工具时，插件会明确停止，不会尝试修改客户端内部文件。

如果 CLI 没有 `plugin add`，可先添加上述 marketplace，再在桌面插件目录选择 **Sidebar Organizer** 安装；或者使用下面的独立 skill。市场条目需要重新打开应用才能出现时，请先保存进行中的工作。

## ZIP 安装：独立 skill

1. 在 [Releases](https://github.com/VeraPyuyi/codex-sidebar-organizer/releases/latest) 下载 `organize-sidebar-skill-0.1.1.zip` 并解压。
2. 将其中完整的 `organize-sidebar` 文件夹复制到技能目录。Windows 默认是 `%USERPROFILE%\.codex\skills\`，macOS/Linux 默认是 `~/.codex/skills/`；自定义了 Codex 主目录时用对应目录。已有同名技能时先备份再替换。
3. 新建桌面会话，选择该技能并发出整理指令。

`sidebar-organizer-plugin-0.1.1.zip` 是标准插件目录包，供支持插件 ZIP 导入的客户端或自行维护 marketplace 的用户使用。不要把插件包当成独立技能文件夹复制。无需同时安装两个版本，避免出现两个同名技能。

## 常用说法

```text
使用 $organize-sidebar，先预览分类方案，不要移动。
使用 $organize-sidebar，把未分类的项目和聊天按来源整理。
使用 $organize-sidebar，再整理一下新增聊天，保留已有分组。
```

首次整理会说明预计移动数量、未知来源和近期列表覆盖范围，随后执行已经请求的操作。默认将聊天设为最近更新时间排序；这是客户端共享的侧边栏偏好，置顶排序和分组显示模式保持原样。

## 0.1.1：修复临时聊天 ID 的核对问题

部分客户端会在分组里显示 `client-new-thread:` 临时 ID，却在最近列表里保留正式 ID。0.1.1 增加只读交叉核对：加载本机 Codex 状态文件，仅提取严格匹配的分组元数据，确认正式聊天已归类后不再重复移动。它不根据标题猜对应关系，也不会写回状态文件。这个兼容适配依赖已验证的本地状态格式；格式缺失或证据冲突时会保留未验证状态并停止相关移动。

本次 Windows 实测独立运行两轮，每轮都正确识别已归类聊天，新增分组 0、移动 0、核对错误 0。原有 5 个分组、23 个项目和 6 条置顶保持不变。此前 20 条无法核实身份的记录仍单独报告为排除项，不计入通过范围。

## 能力边界

- **支持范围：** 提供原生分组工具的 Codex 桌面会话。安装本插件不会为独立 CLI、ChatGPT 网页或不支持的旧版本新增侧边栏接口。
- **历史覆盖：** 已验证的列表工具最多返回 50 条非置顶聊天，没有历史分页。技能会检查是否还有获准的历史读取方式；无法读取的更早聊天明确列为未覆盖，总量未知。项目数量、聊天数量均动态读取，不硬编码作者的账户规模。
- **来源含义：** 云端记录不代表由某台电脑或网页创建。本机标签指当前执行主机。无法可靠路由的后台记录会跳过，避免生成不可见的“空分类”。
- **折叠和打开：** 元数据核对不能证明 UI 可见或可打开。没有支持的界面能力时，会提示手动点击标题收起，不声称已完成自动折叠。
- **同步与定时：** 不承诺其他电脑或网页版同步，不自动创建后台定时任务。
- **结果：** 助手会报告已移动、保留、跳过和未验证数量。操作失败或期间状态改变时重新读取，避免盲目重试。

## 隐私与实现

插件没有网络客户端、遥测、凭据或远程执行服务，只使用宿主已有的桌面工具。助手可能在本机临时目录保存 ID、路径和分组信息以供核对；这些属于私人记录，不应提交到 GitHub。插件不要求读取聊天正文。宿主 Codex/ChatGPT 的服务和数据处理方式仍由宿主决定。

存在临时 ID 时，可选辅助程序还会只读加载当前 Codex 主目录中的 `.codex-global-state.json`，从中提取匹配的分组记录作为证据。不会导出该文件的其他设置，不会搜集其他账户或历史备份。

可选的 Python 3.10+ 辅助程序只生成分类方案、核对前后元数据，不操作应用。没有 Python 时，助手可按技能规则直接使用原生工具。代码和测试全部使用虚构数据。

## 开发与验证

```sh
python -m unittest discover -s tests -v
python scripts/build_release.py
```

构建会校验包结构、仅收录明确允许的文件、生成插件和技能 ZIP 及 `SHA256SUMS.txt`，并重新解压运行辅助程序。GitHub Actions 在 Windows 与 Linux 上验证合成场景。新客户端的完整 UI 操作仍需实际验收；测试通过不代表所有客户端都提供所需工具。

参见 [测试范围](docs/VALIDATION.md) 和 [原生工具约定](plugins/sidebar-organizer/skills/organize-sidebar/references/native-tools.md)。插件格式和分发方式依据 [OpenAI 插件文档](https://developers.openai.com/plugins/build/plugins)；技能格式参见 [官方技能文档](https://developers.openai.com/plugins/build/skills)。本项目为社区项目，与 OpenAI 没有隶属关系。

MIT License · [提交问题](https://github.com/VeraPyuyi/codex-sidebar-organizer/issues)（请勿附带真实聊天内容、原始快照或凭据）。
