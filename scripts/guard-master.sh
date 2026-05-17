#!/bin/sh
# guard-master.sh — Master 分支安全守卫
# Usage: guard-master.sh [--block|--warn]
#   --block  Exit 1 if on master (blocks the operation). Default.
#   --warn   Exit 0 but print warning if on master.

MODE="${1:---block}"
BRANCH=$(git branch --show-current 2>/dev/null)

if [ "$BRANCH" = "master" ] || [ "$BRANCH" = "main" ]; then
    echo ""
    echo "=============================================================="
    echo "  !!! 警告: 当前在 $BRANCH 分支上 !!!"
    echo "=============================================================="
    echo ""
    echo "  开发工作应在 feature-dev 分支上进行。"
    echo ""
    echo "  如需转移当前修改，运行救援脚本:"
    echo "    bash scripts/rescue-from-master.sh"
    echo ""
    if [ "$MODE" = "--block" ]; then
        echo "  [操作已阻止]"
        exit 1
    else
        echo "  [仅警告，操作继续]"
        exit 0
    fi
fi
exit 0
