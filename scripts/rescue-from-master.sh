#!/bin/sh
# rescue-from-master.sh
# 将 master 分支上所有未提交的修改转移到 feature-dev 分支
# 可安全从任意分支运行

set -e

CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)

if [ "$CURRENT_BRANCH" != "master" ] && [ "$CURRENT_BRANCH" != "main" ]; then
    echo "当前在 $CURRENT_BRANCH 分支上，不在 master/main。无需救援。"
    exit 0
fi

# 检查是否有未完成的合并
if [ -f ".git/MERGE_HEAD" ]; then
    echo "错误: 存在未完成的合并。请先处理合并冲突。"
    exit 1
fi

# 检查是否有任何变更
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "没有未提交的变更。无需救援。"
    exit 0
fi

echo "正在保存当前修改并切换到 feature-dev 分支..."

git stash -u

if ! git checkout feature-dev; then
    echo "错误: 无法切换到 feature-dev 分支。"
    echo "请手动创建: git checkout -b feature-dev"
    exit 1
fi

if ! git stash pop; then
    echo ""
    echo "警告: stash 应用时发生冲突。"
    echo "请手动解决冲突后执行: git stash drop"
    echo ""
    git status --short
    exit 1
fi

echo ""
echo "成功! 所有修改已转移到 feature-dev 分支。"
