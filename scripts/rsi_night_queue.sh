#!/bin/bash
# RSI 夜间无人值守队列
#
# 设计要点
# --------
# 1. 单一入口：所有任务串行，绝不并发（并发会让 opencode 互相覆盖、进程互杀）
# 2. 每组前后做健康检查：进程、磁盘、残留、结果完整性
# 3. 自愈：单组失败重试 2 次；连续 3 组失败则跳过该任务并记账
# 4. 断点续跑：已存在 resume.json 且状态为 stage_complete 的组直接跳过
# 5. 全程写结构化日志，便于早上汇总
#
# 用法
# ----
#   nohup setsid bash scripts/rsi_night_queue.sh >/dev/null 2>&1 </dev/null &
# 监控
#   tail -f /root/rsi-night/queue.log
#   cat /root/rsi-night/status.tsv

set -u

# ── 配置 ──────────────────────────────────────────────────────────────
GOV=/root/rsi-m01/governance/docs/governance
BENCH=$GOV/scripts/rsi_realworld_benchmark.py
METRICS=$GOV/scripts/rsi_quality_metrics.py
SUITE=$GOV/docs/experiments/rsi-realworld/tasks.json
OPENCODE=/root/.opencode/bin/opencode
MODEL=<推理端点>/<模型>
export RSI_OPENCODE_BASE_CONFIG=/root/rsi-preflight/base-config.json

ROOT=/root/rsi-night
LOG=$ROOT/queue.log
STATUS=$ROOT/status.tsv
TASKS_FILE=$ROOT/tasks.list
ROUNDS=${ROUNDS:-5}
MAX_TRY=3
DISK_MIN_GB=3

mkdir -p "$ROOT"
: >> "$LOG"
[ -f "$STATUS" ] || printf 'ts\ttask\tarm\tround\tphase\tstatus\telapsed\ttry\n' > "$STATUS"

log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ── 健康检查 ──────────────────────────────────────────────────────────
health() {
    local tag=$1
    # 磁盘
    local avail
    avail=$(df -BG --output=avail /root 2>/dev/null | tail -1 | tr -dc '0-9')
    if [ -n "$avail" ] && [ "$avail" -lt "$DISK_MIN_GB" ]; then
        log "[HEALTH] $tag 磁盘仅剩 ${avail}G，低于 ${DISK_MIN_GB}G 阈值"
        return 1
    fi
    # 孤儿进程（本脚本之外不该有 rsi_realworld 在跑）
    local orphans
    orphans=$(pgrep -fc 'rsi_realworld_benchmark.py run' 2>/dev/null || echo 0)
    if [ "$orphans" -gt 1 ]; then
        log "[HEALTH] $tag 发现 $orphans 个 benchmark 进程，清理多余"
        pgrep -f 'rsi_realworld_benchmark.py run' | tail -n +2 | xargs -r kill -9 2>/dev/null
    fi
    # opencode 残留一律清掉（它会挂在 epoll 不退出）
    pkill -9 -f 'opencode run' 2>/dev/null || true
    return 0
}

# ── 准备工作目录 ──────────────────────────────────────────────────────
# 首次运行时从 rsi-night-src 复制冻结源；governance 组额外挂治理骨架。
prepare_work() {
    local task=$1 arm=$2 work=$3
    if [ ! -d "$work/sources" ]; then
        local src=/root/rsi-night-src/$task/$arm/sources
        if [ ! -d "$src" ]; then
            log "[PREP] 缺少源目录 $src，跳过"
            return 1
        fi
        cp -r "$src" "$work/"
        chmod -R u+w "$work/sources" 2>/dev/null
        log "[PREP] $task/$arm 源已就位（$(ls "$work/sources" | wc -l) 个文件）"
    fi
    if [ "$arm" = "governance" ] && [ ! -d "$work/docs" ]; then
        ( cd /root/rsi-m01/governance && tar cf - --exclude=sources --exclude=stage1.md \
            --exclude=report.md --exclude=evidence.json --exclude='.rsi-prompt-*' . 2>/dev/null ) \
          | ( cd "$work" && tar xf - 2>/dev/null )
        chmod -R u+w "$work/docs" 2>/dev/null
        log "[PREP] $task/$arm 治理骨架已挂载"
    fi
    return 0
}

# ── 单阶段执行 ────────────────────────────────────────────────────────
run_phase() {
    local task=$1 arm=$2 round=$3 phase=$4
    local work=$5 out=$6
    local i rc
    for i in $(seq 1 $MAX_TRY); do
        [ "$phase" = "init" ] && rm -rf "$out"
        log "  -> $task $arm r$round $phase try$i"
        timeout 1800 python3 "$BENCH" run --task "$task" --phase "$phase" --arm "$arm" \
            --timeout 900 --work "$work" --out "$out" \
            --opencode "$OPENCODE" --model "$MODEL" >> "$ROOT/bench.log" 2>&1
        rc=$?
        if [ $rc -eq 0 ]; then
            return 0
        fi
        log "  !! $task $arm r$round $phase try$i rc=$rc"
        ( cd "$work" && rm -f .rsi-prompt-*.txt 2>/dev/null )
        pkill -9 -f 'opencode run' 2>/dev/null || true
        sleep 45
    done
    return 1
}

# ── 主循环 ────────────────────────────────────────────────────────────
TASKS=$(cat "$TASKS_FILE" 2>/dev/null)
if [ -z "$TASKS" ]; then
    log "FATAL: $TASKS_FILE 为空或不存在"
    exit 2
fi
log "队列启动：$(echo "$TASKS" | wc -w) 个任务 × ${ROUNDS} 轮 × 2 组"

for task in $TASKS; do
    family=$(echo "$task" | cut -d- -f1)
    consec_fail=0
    for round in $(seq 1 "$ROUNDS"); do
        for arm in baseline governance; do
            # 结果目录必须在 work 之外；执行器要求 out 事先不存在
            work=$ROOT/$task/r$round/$arm
            out=$ROOT/$task/r$round/out-$arm
            mkdir -p "$work"
            rm -rf "$out"

            # 断点续跑：已完成则跳过
            if [ -f "$out/resume.json" ] && grep -q '"status": "stage_complete"' "$out/resume.json" 2>/dev/null; then
                log "SKIP $task $arm r$round（已完成）"
                continue
            fi

            health "$task/$arm/r$round" || { sleep 60; health "$task/$arm/r$round"; }

            if ! prepare_work "$task" "$arm" "$work"; then
                consec_fail=$((consec_fail + 1))
                continue
            fi

            local_start=$(date +%s)
            if run_phase "$task" "$arm" "$round" init "$work" "$out" \
               && run_phase "$task" "$arm" "$round" resume "$work" "$out"; then
                el=$(( $(date +%s) - local_start ))
                st=$(python3 -c "import json;print(json.load(open('$out/resume.json')).get('status','?'))" 2>/dev/null || echo '?')
                printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
                    "$(date '+%F %T')" "$task" "$arm" "$round" "both" "$st" "$el" "ok" >> "$STATUS"
                # 质量指标
                python3 "$METRICS" --suite "$SUITE" --task "$task" --work "$work" \
                    --out "$out/quality.json" >> "$LOG" 2>&1 || log "  (指标计算失败，不影响主流程)"
                log "OK   $task $arm r$round $st ${el}s"
                consec_fail=0
            else
                el=$(( $(date +%s) - local_start ))
                printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
                    "$(date '+%F %T')" "$task" "$arm" "$round" "both" "FAILED" "$el" "fail" >> "$STATUS"
                log "FAIL $task $arm r$round ${el}s"
                consec_fail=$((consec_fail + 1))
                if [ "$consec_fail" -ge 3 ]; then
                    log "ABORT 任务 $task 连续 $consec_fail 组失败，跳过剩余轮次"
                    break 2
                fi
            fi
            health "$task/$arm/r$round"
            sleep 5
        done
    done
done

log "队列结束"
