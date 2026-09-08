[English](./README.en.md) · [Website](https://provena.lei6393.com) · [GitHub](https://github.com/SuperMarioYL/provena)

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/hero-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/hero-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/hero-dark.svg">
  <img src="./assets/presentation/hero-light.svg" width="960" alt="Hero diagram">
</picture>

# provena

**来源变化时标记依赖结论。**

Provena 在图中记录结论、来源片段与结论依赖，并在被跟踪内容变化时传播 stale 状态。

## 为什么需要它

结论可能在支撑它的文件片段变化后继续被使用。明确依赖边可以指出哪些结论需要重新检查。

- **明确来源关联** — 结论关联可检查来源对象。
- **传递失效标记** — 下游结论也会被标为待检查。
- **无需模型** — 哈希比较与图遍历具有确定性。

## 架构

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/architecture-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-dark.svg">
  <img src="./assets/presentation/architecture-light.svg" width="960" alt="Architecture diagram">
</picture>

record_claim 在 ClaimDependencyGraph 中登记来源片段与边；CascadeEngine 比较当前和记录哈希，再沿反向结论依赖遍历，将受影响结论标为 stale。可选 UI 展示这些状态。

| 组件 | 职责 |
| --- | --- |
| `Source spans` | provena/core/source.py |
| `Claim graph` | provena/core/graph.py |
| `Mutation check` | provena/core/cascade.py |
| `Stale claims` | Local graph / UI |

## 安装与快速上手

使用仓库清单指定的运行时版本构建，并在仓库根目录运行示例。

```bash
git clone https://github.com/SuperMarioYL/provena.git
cd provena
uv venv .venv
uv pip install --python .venv/bin/python -e .
source .venv/bin/activate
```

创建临时单行来源与两条依赖结论，将 limit=10 改为 limit=20，再检查传播状态。

```bash
.venv/bin/python examples/presentation-demo.py
```

## 实际运行示例

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/process-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/process-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/process-dark.svg">
  <img src="./assets/presentation/process-light.svg" width="960" alt="Process diagram">
</picture>

Changing the source marks both limit and request claims stale.

```text
before: {"limit": "fresh", "request": "fresh"}
flagged: ['limit', 'request']
after: {"limit": "stale", "request": "stale"}
```

完整命令与输出保存在 [docs/demo-results.json](./docs/demo-results.json). 输入和复现代码均随仓提供。

![已有终端录制](./assets/demo.gif)

保留已有录制供参考；上方文字示例给出当前可复现的操作。

## 用法

CLI 提供以下操作。示例之外的命令需要替换成你的文件路径或标识。

```bash
provena graph --json
provena check
# Interactive local demo server:
provena demo
```

## 配置

使用 FileSpan.from_file(path, start, end) 捕获来源片段。record_claim 接受 grounded_on 来源对象或已登记 ID，以及 depends_on 结论 ID。集成方应负责图持久化及收到 stale 后的重新推导。

## 集成与职责分工

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/integrations-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-dark.svg">
  <img src="./assets/presentation/integrations-light.svg" width="960" alt="Integrations diagram">
</picture>

以下路径已有源码实现。按任务选择输入，并把生成的结果与项目一起保存。

| 路径 | 已实现职责 |
| --- | --- |
| FileSpan | Tracked file line ranges |
| Claim recording | Grounding and dependencies |
| Cascade callback | Application notification seam |
| JSON / local UI | Graph inspection |

## 限制与后续方向

- 引擎标记待检查结论，不会自动重新推导或纠正。
- 依赖由调用者提供，不证明来源确实支持结论。
- 编辑后文件行片段可能移动；来源选择与图完整性影响失效标记的作用。

自动重新推导和更多来源适配属于后续集成；当前核心负责记录与 stale 传播。

## 许可与贡献

许可见 [LICENSE](./LICENSE). 反馈问题时请提供最小输入、执行命令和实际输出。
