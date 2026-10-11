# Sidebar Organizer 0.1.1

修复临时聊天 ID 导致已经归类的聊天再次被计划移动、自动核对失败的问题。

- 新增只读本机分组证据核对：严格匹配分组 ID、名称、成员和正式聊天 ID；不按标题猜身份。
- 对每次运行的前后状态分别取证，拒绝过期、冲突、跨主机或账户范围不唯一的证据。
- 无法确认的临时 ID 会阻止相关移动；原有置顶、项目归属和手工分组继续受到保护。
- 37 项测试通过；两个 ZIP 解压后运行新版核对逻辑。
- 两轮本机实测均为：新增分组 0、移动 0、核对错误 0。已有 5 个分组、23 个项目和 6 条置顶保持不变。

**覆盖范围仍如实保留：** 20 条此前无法确认的后台记录仍列为排除项；近期列表之外的历史、自动折叠和跨设备同步未因此变为已验证。总体报告可为 `incomplete`，同时显示本轮操作核对通过。

**兼容性说明：** 临时 ID 适配器只读加载当前本机 Codex 状态文件，提取匹配的分组字段；不会修改该文件。它依赖本地状态格式，未知格式或冲突会停止相关移动。

下载 `organize-sidebar-skill-0.1.1.zip` 安装独立 skill，或使用 `sidebar-organizer-plugin-0.1.1.zip`。`SHA256SUMS.txt` 提供校验值。

使用插件版且此前安装了 `--ref v0.1.0` 的用户，执行以下已验证的升级步骤，然后新建桌面会话加载新版技能：

```sh
codex plugin marketplace remove sidebar-organizer-marketplace
codex plugin marketplace add VeraPyuyi/codex-sidebar-organizer --ref v0.1.1
codex plugin add sidebar-organizer@sidebar-organizer-marketplace
```

安装及升级说明见 [中文说明](https://github.com/VeraPyuyi/codex-sidebar-organizer#readme) / [English](https://github.com/VeraPyuyi/codex-sidebar-organizer/blob/main/README.en.md)。
