# Plan Mode SOP (v4)

**触发**：3步以上有依赖/多文件/条件分支 | **跳过**：1-2步直接做

---

## 启动（收到plan指令后立即执行）

```python
# 第一个工具调用必须是这个，禁止跳过
import os; os.makedirs('./plan_XXX', exist_ok=True)
handler.enter_plan_mode('./plan_XXX/plan.md')
```
⛔ 未完成此步前禁止任何其他操作（包括探索、写plan、启动subagent）

---

## Phase 1: 探索（subagent only）

主agent禁止直接探测环境。委托subagent只读探测，产出 `exploration_findings.md`。

1. 从L1匹配SOP + update_working_checkpoint
2. 启动探索subagent（`--verbose`监察模式）：
   - 任务：探测环境，写 `exploration_findings.md`（现状/发现/风险）
   - 约束：只读，≤10次工具调用
3. 监察：读output.txt → 纠偏(`_intervene`/`_keyinfo`/`_stop`) → 收取findings

---

## Phase 2: 规划（主agent）

读匹配SOP + exploration_findings → 写 plan.md：

```markdown
<!-- EXEC PROTOCOL (每轮必读)
0. file_read(plan.md) → update_working_checkpoint
1. 找到下一个可启动Group（前置依赖已完成）
2. 启动subagent执行该Group → 监察output → 纠偏
3. subagent完成 → 确认验收 → file_patch打✓ → 更新working memory → 回0
⛔ 主agent不搬砖只监察 | 禁凭记忆 | 禁跳验证 -->
# 任务标题
需求：... | 约束：...

## 探索发现
- ...

## 执行计划
### Group A (描述)
1. [ ] 步骤描述 (SOP: xxx_sop.md)
2. [ ] 步骤描述 (依赖:1)

### Group B (独立，可与A并行)
3. [ ] 步骤描述

### Group C (依赖:A,B)
4. [ ] 步骤描述 (依赖:2,3)

## 验证
N. [ ] [VERIFY] 独立subagent对抗验证 (SOP: verify_sop.md)
```

**分组规则**：
- 强依赖链（后步直接用前步产出）→ 合并为一个 Group → 一个 subagent
- 无依赖的步骤 → 独立 Group → 可并行启动（≤3并发）
- `[?]` 条件步骤：写明分支条件，未选标[SKIP]

**自检**：探索发现→plan覆盖？SOP标注？依赖正确？Group划分合理？有[VERIFY]？

**门禁**：ask_user确认 → 注册done_hook（含working memory初始值）→ 结束Plan阶段：
```python
code_run({'inline_eval': True, 'script': '''handler._done_hooks.append(
    "Plan完成。执行：\\n"
    "1. update_working_checkpoint('[MODE]EXEC | plan:./plan_XXX/plan.md | 不搬砖只监察 | ≤3并发')\\n"
    "2. file_read(plan.md)，按EXEC PROTOCOL启动第一个Group的subagent。"
)'''})
```

---

## Phase 3: 执行（监察者模式）

**角色**：主agent = 监察者，全部具体工作由subagent完成。
**操作手册**：`supervisor_sop.md`（红线/监控循环/干预时机/干预原则）

⛔ 主agent禁止：写代码/改文件/跑命令/直接执行任何交付物相关操作
✅ 主agent只做：分发Group → 监察output → 纠偏干预 → 打✓ → 更新working memory → 汇总

### 执行循环

```
读plan → 找可启动Group → 启动subagent → 监察 → 验收打✓ → 更新memory → repeat
```

1. **分发**：对每个可启动Group，启动subagent（`--verbose`），input包含：
   - Group内所有步骤 + 相关SOP路径 + 前置Group的产出摘要
2. **监察**：读output.txt，审查进度和方向
   - 方向偏 → `_intervene` 纠正
   - 缺上下文 → `_keyinfo` 注入
   - 卡死/跑飞 → `_stop` 终止重启
3. **验收打✓**：subagent完成后，主agent确认产出正确 → `file_patch` plan.md 标 `[✓]`
4. **更新memory**：`update_working_checkpoint` 更新进度

### Working Memory 规范

每轮 update_working_checkpoint，格式：
```
[MODE] EXEC | plan: ./plan_XXX/plan.md
[PROGRESS] GroupA✓ GroupB(running) | 当前: subagent执行步骤3
[CONTEXT] 关键产出/路径/发现（从subagent output提取）
[RULE] 不搬砖只监察 | ≤3并发 | 失败→查stderr重启≤2次
```

### 终止检查

最后一个Group完成 → file_read(plan.md) 全文扫描 → 确认0个`[ ]`残留 → 进入Phase 4

---

## Phase 4: 验证（独立subagent）

1. 创建 `verify_context.json`（任务描述/plan路径/交付物/必做检查）
2. 启动验证subagent：对抗性验证，每项必须有工具调用证据
3. 读取 VERDICT: PASS/FAIL/PARTIAL
   - PASS → 标[VERIFY]为[✓]，任务完成 🏁
   - FAIL → 提取失败项追加[FIX]步骤 → 委托subagent修复 → 重新验证（最多2轮）

---

## 硬约束（全阶段生效）

- 主agent上下文是最稀缺资源，具体工作全部委托subagent
- 主agent唯一允许的写操作：plan.md打✓、working memory更新、干预文件
- 每步必须有独立完成判据
- 不可逆操作前多验证一步
- subagent失败：查stderr→修正重启，最多2次
- 步骤失败：后续依赖标[SKIP]，plan有误回Phase 2修正