#!/bin/bash
###
 # @Author: Await
 # @Date: 2025-06-20 14:08:11
 # @LastEditors: Await
 # @LastEditTime: 2025-06-20 16:25:44
 # @Description: 请填写简介
### 

# 推送到所有远程仓库的脚本
echo "=== 开始推送到所有远程仓库 ==="

# 获取当前分支名
BRANCH=$(git branch --show-current)
echo "当前分支: $BRANCH"

# 定义远程仓库列表
REMOTES=("origin" "new-gogs" "test-repo")

# 推送到每个远程仓库
for remote in "${REMOTES[@]}"; do
    echo ""
    echo "推送到 $remote..."
    if git push $remote $BRANCH; then
        echo "✅ 成功推送到 $remote"
    else
        echo "❌ 推送到 $remote 失败"
    fi
done

echo ""
echo "=== 推送完成 ==="

# 显示所有远程仓库状态
echo ""
echo "=== 远程仓库状态 ==="
git remote -v 