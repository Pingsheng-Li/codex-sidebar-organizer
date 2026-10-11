# Sidebar Organizer 0.1.3

新增侧边栏刷新核对，以及用户明确要求后启用的后台定时检查。

- 新增只读 `refresh-check`：比较当前原生聊天列表与分组引用，报告待核对项。列表遗漏、来源故障、手动移出分组均不会被认定为删除。
- 支持按需创建或复用原生后台核对任务，默认每小时一次；无变化保持安静，出现新的待核对项或有意义的故障时提醒。安装插件不会自动开启任务。
- 刷新检查不建立分组、不移动、不删除聊天；既有分类、临时 ID 与 Codex 云端识别功能保留。
- 61 项自动测试通过；两个 ZIP 解压后验证刷新检查和原有流程，并通过隔离环境安装与技能校验。

**尚不支持网页删除后的自动清理。** 当前桌面原生工具没有提供强制缓存刷新、权威删除状态或独立清理残留引用的操作。聊天未出现在最近 50 条里不能证明已删除；无法确认的记录全部保留。定时核对不等于删除同步，不承诺实时性或完整历史覆盖。

## 安装或升级

旧版插件用户先执行第一条命令移除本插件的旧市场注册；首次安装用户跳过第一条。随后新建桌面会话加载新版技能。

```sh
codex plugin marketplace remove sidebar-organizer-marketplace
codex plugin marketplace add VeraPyuyi/codex-sidebar-organizer --ref v0.1.3
codex plugin add sidebar-organizer@sidebar-organizer-marketplace
```

独立 skill 用户下载 `organize-sidebar-skill-0.1.3.zip`，备份并替换同名技能文件夹。`sidebar-organizer-plugin-0.1.3.zip` 为插件目录包；`SHA256SUMS.txt` 提供校验值。选择一种安装方式即可。

[中文说明](https://github.com/VeraPyuyi/codex-sidebar-organizer#readme) · [English](https://github.com/VeraPyuyi/codex-sidebar-organizer/blob/main/README.en.md) · [验证范围](https://github.com/VeraPyuyi/codex-sidebar-organizer/blob/main/docs/VALIDATION.md)
