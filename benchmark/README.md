# 治理 Benchmark 测试用例集

> 用于共享、复用、扩充治理评测用例。所有素材**可复现**（固定包 + 哈希），
> 第三方源码采用**允许开源分发**的授权，可安全对外发布。

## 这是什么

`docs/experiments/` 下的内部 benchmark 是**运行产物**（结果、日志、叙事），
不适合直接分享。本目录把它们拆成**自包含的测试用例**：

- 每个任务一个目录，带 `task.md`（说明）+ `ground-truth.yaml`（标准答案）+ `grade.py`（判据）
- 素材**内嵌**（`source/`）或**生成脚本**（`fixtures/`），无需本机依赖
- 哈希口径固化在 `ground-truth.yaml`，跑前先校验、防输入漂移

## 任务一览

| 任务 | 类别 | 权威性 | 规模 | 素材 |
|---|---|---:|---:|---|
| **J3b-filemanage-plugin** | 代码审计 | **A**（穷举 + 四轮方差） | 1,725 行 | Z-Blog v2.2 插件，已内嵌 |
| **T04-vuln-analysis** | 代码审计 | **B**（6×2 轮） | 1 个 `app.py` | 自制合成样本，已内嵌 |
| **T05-vuln-deep** | 代码审计 | **B**（难度不足） | 1 个 `app.py` | 自制合成样本，已内嵌 |

### A 级 vs B 级

- **A 级**：GT 经过被测模型反推修正，驳回项留了证据链；素材可穷举，有方差数据
- **B 级**：素材可复现但范围不可穷举，或难度不足（达成率饱和）

## 运行 J3b（A 级，推荐起点）

```bash
cd benchmark/tasks/J3b-filemanage-plugin

# 1. AI 在 source/ 里审计，按 task.md 产出 findings.json + summary.md
# 2. 判据（grade.py 零依赖，不引 pyyaml）
python grade.py --findings findings.json --truth ground-truth.yaml

# 可选：输出待复核项
python grade.py --findings findings.json --truth ground-truth.yaml --review
```

判据口径（见 `grade.py`）：

- `recall` = L1 命中数 / L1 总数（唯一进达成判定的质量指标）
- `precision` = 命中任意 GT 的 finding 数 / finding 总数
- `score` = min(1.0, 0.45*recall + 0.25*precision + 0.20*fix + 0.10*l2_bonus)
- `achieved` = recall ≥ 0.8 且 precision ≥ 0.6

### 素材哈希

`ground-truth.yaml` 的 `source:` 块固化了三档哈希：

- `archive_sha256`：Z-Blog v2.2 完整包（如需完整环境）
- `source_tree_sha256`：解压后全树 `*.asp`
- `scope_sha256`：**仅本任务 4 个 ASP**（`a5fe5cb5...`），跑前先校验

## 授权

| 素材 | 来源 | 授权 |
|---|---|---|
| Z-Blog v2.2（J3b） | rainbowsoft.org | **官方 EULA 允许完全开源分发**；须保留官方署名/链接标识 |
| T04 / T05 fixtures | 本项目自制合成样本 | 同本仓库 LICENSE |

## 扩充用例

新加任务时：

1. 建 `tasks/<task-id>/`，放 `task.md` + `ground-truth.yaml` + `grade.py`
2. 素材内嵌到 `source/`（小文件）或写 `prepare.sh` 下载（大文件/外部依赖）
3. `ground-truth.yaml` 顶部写 `source:` 块，固化素材哈希
4. 更新本文的"任务一览"表
