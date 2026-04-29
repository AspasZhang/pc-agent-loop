# Plan Mode SOP v3

**触发**：3步以上有依赖/多文件协同/条件分支/需并行 | **禁用**：1-2步简单任务直接做
工作目录：`./plan_XXX/`（XXX=任务英文短名）
入口：`handler.enter_plan_mode("./plan_XXX/plan.md")`

---

## 一、Plan 阶段

进入时立即：
```
update_working_checkpoint("[MODE] PLAN | 任务: XXX | 禁止: 写文件/执行命令/启动执行subagent | 只做: 探索+提问+写plan")
```

### 1. 探索（只读）

启动探索 subagent 收集事实：
```bash
# input: 探索目标+关注点，限制≤10轮
python agentmain.py --task plan_XXX_explore --input "探索目标..." --bg --verbose
```
监察 output.txt，提取关键发现。主 agent 可补充少量只读操作（读文件/dry-run）。

**结束标志**：所有可发现的事实已收集，剩余未知项都需要用户决策。

### 2. 提问直到 Decision-Complete

持续 ask_user 直到能写出完整方案。

**提问规则**：
- 只问会实质改变 plan 的问题，不问废话
- 优先 ask_user + candidates（2-4选项 + 推荐默认值），极少数才纯文字提问
- 可发现的事实先探索，探索不到再问（带候选项）
- 偏好/权衡直接问
- 用户不答 → 按推荐默认值继续，plan 中标记为假设

**必须覆盖的维度**（按需选做，不机械全问）：
目标+成功标准 | 范围边界 | 约束 | 技术方案 | 任务拆分 | 验证标准

**结束标志**：方案足够详细，subagent 拿到后零决策即可实现。

### 3. 写 plan.md + 用户确认

写入 `./plan_XXX/plan.md`，格式：

```markdown
# 任务标题
## 概要
一句话目标+方案

## 步骤
1. [步骤名] 描述（所有权: 文件列表）
   依赖: 无 | 验证: 怎么确认做对了
2. [步骤名] 描述 [P=可并行]
   依赖: 1 | 验证: ...
...
N. [VERIFY] 全量验证（验证标准描述）

## 假设
- 假设1（用户未明确，按默认值处理）

## 验证标准
- 最终交付物怎么算通过
```

然后：
```
ask_user("Plan 已就绪", candidates=["确认执行", "我要修改", "取消"])
```
- 修改 → 继续对话，新 plan 完整替换
- 确认 → 进入 Execute 阶段

---

## 二、Execute 阶段（监察者模式）

用户确认后立即切换：
```
update_working_checkpoint("[MODE] EXEC | N步 | 1.[ ] xxx 2.[ ] yyy ... | ≤3并发 | 不搬砖只监察")
```

### 硬性规则

⛔ **主 agent 禁止自己执行具体任务**

工具调用白名单（Execute 阶段主 agent 只允许以下操作）：
- ✅ `code_run`: 仅限 `python agentmain.py` 启动subagent / `sleep` / `cat output.txt`
- ✅ `file_read`: 仅限 output*.txt / plan.md / 干预文件(_keyinfo/_intervene/_stop)
- ✅ `file_write/file_patch`: 仅限干预文件 / plan.md 微调
- ✅ `ask_user` / `update_working_checkpoint`
- ⛔ **其他一切禁止**：写代码文件=违规，执行业务命令=违规，自己mv/cp/mkdir=违规

> ⚠️ **自检**：你在自己写代码/移文件/跑业务命令吗？停。启动 subagent。

### 执行循环

**1. 分发任务**

对每个无前置依赖（或依赖已完成）的步骤，启动 subagent：

```bash
# input 包含：步骤描述 + 前置步骤产出 + 文件路径
# prompt 中告诉 subagent：把你的任务目标放到 working memory 里
python agentmain.py --task plan_XXX_stepN --input "..." --bg --verbose
```

input 要点：
- 从 plan.md 提取该步骤的完整描述
- 附上前置步骤的实际产出（路径/关键结果）
- 明确所有权范围（你负责哪些文件）
- 告诉 subagent："第一步把任务目标写入 working memory"
- 同时运行 ≤3 个 subagent

**2. 监察循环**

```
while 存在未完成步骤:
  读活跃 subagent 的 output.txt
  评估状态:
    正常推进 → 继续
    方向偏离 → _intervene 纠正
    缺上下文 → _keyinfo 注入
    卡住/失败 → _stop，分析原因，重启或换方案
    完成 → 读结果，更新 working memory:
      "[MODE] EXEC | N步 | 1.[✓] 2.[✓] 3.[→PID] 4.[ ] ..."
  新步骤依赖满足 → 启动新 subagent
```

**3. 异常处理**

- subagent 连续失败：微调 plan 该步骤描述（允许），重启 subagent
- plan 级问题（方案不可行）：ask_user 确认调整方向
- 8 轮未更新 working memory → 强制重读 plan.md 同步状态

### 验证

所有执行步骤完成后，启动独立验证 subagent：

```bash
# input: 任务描述 + plan.md路径 + 交付物清单 + 验证标准
# 告诉它读 verify_sop.md
python agentmain.py --task plan_XXX_verify --input "你是独立验证者。读 ../memory/verify_sop.md 执行对抗性验证。任务: ... 交付物: ... 验证标准: ..." --bg --verbose
```

**验证 subagent 规则**：
- 独立运行，主 agent 只观察 output.txt，**禁止 _intervene**
- 只有卡死（≥15轮无产出）才允许 _stop 终止重启
- 验证 subagent 只验证不修改文件

**验证结果处理**：
- PASS → 任务完成，汇总给用户
- FAIL → 主 agent 根据失败项启动修复 subagent，修复后**再验证一次**
- 二次 FAIL → ask_user 交给用户决定

---

## 三、Working Memory 格式参考

Plan 阶段：
```
[MODE] PLAN | 任务: Flask重构 | 禁止写文件执行命令 | 已探索: 5路由2模型 | 待确认: 异步方案
```

Execute 阶段：
```
[MODE] EXEC | 5步完成2 | 1.[✓]骨架 2.[✓]数据层 3.[→]路由PID:1234 4.[ ]订单 5.[ ]验证 | ⛔自己写代码/移文件=违规，只能启动subagent/读output/写干预文件
```

验证阶段：
```
[MODE] VERIFY | 验证subagent PID:5678 运行中 | 禁止干预 | 只观察
```