#!/usr/bin/env python3
"""
QuestBoard 重命名替换脚本
批量替换所有代码文件中的朝廷术语为冒险团术语
"""

import re
import pathlib
from pathlib import Path

# 项目根目录
BASE = Path("/home/impulse/workspace/github/yangwang")

# 术语映射表
REPLACEMENTS = {
    # Agent IDs (pinyin -> new)
    r"\btaizi\b": "vice",
    r"\bzhongshu\b": "strategy",
    r"\bmenxia\b": "review",
    r"\bshangshu\b": "dispatch",
    r"\bhubu\b": "finance",
    r"\blibu\b(?!_hr)": "scribe",  # scribe 但不包括 hr
    r"\bbingbu\b": "combat",
    r"\bxingbu\b": "audit",
    r"\bgongbu\b": "build",
    r"\blibu_hr\b": "hr",
    r"\bzaochao\b": "intel",
    # State codes (英文标识符)
    r"'Vice'": "'Vice'",
    r'"Vice"': '"Vice"',
    r"'Strategy'": "'Strategy'",
    r'"Strategy"': '"Strategy"',
    r"'Review'": "'Review'",
    r'"Review"': '"Review"',
    # 中文术语 - 角色
    r"团长": "团长",
    r"副团长": "副团长",
    r"策划部": "策划部",
    r"策划部长": "策划部长",
    r"监察部": "监察部",
    r"监察部长": "监察部长",
    r"调度部": "调度部",
    r"调度部长": "调度部长",
    r"财务小队": "财务小队",
    r"财务小队队长": "财务小队队长",
    r"书记小队": "书记小队",
    r"书记小队队长": "书记小队队长",
    r"战斗小队": "战斗小队",
    r"战斗小队队长": "战斗小队队长",
    r"审判小队": "审判小队",
    r"审判小队队长": "审判小队队长",
    r"建设小队": "建设小队",
    r"建设小队队长": "建设小队队长",
    r"人事小队": "人事小队",
    r"人事小队队长": "人事小队队长",
    r"情报官": "情报官",
    r"情报部": "情报部",
    r"情报官": "情报官",
    # 中文术语 - 流程
    r"委托": "委托",
    r"任务": "任务",
    r"战报": "战报",
    r"驳回": "驳回",
    r"批准": "批准",
    r"回报": "回报",
    r"发布委托": "发布委托",
    r"传达委托": "传达委托",
    r"接令": "接令",
    r"已接令": "已接令",
    r"过目": "过目",
    r"审批": "审批",
    # 中文术语 - 组织
    r"核心部": "核心部",
    r"各小队": "各小队",
    r"公会大厅": "公会大厅",
    r"晨报": "晨报",
    r"副团长": "副团长",
    r"S级": "S级",
    r"A级": "A级",
    r"B级": "B级",
    # 中文术语 - 状态
    r"副团长分拣": "副团长分拣",
    r"策划起草": "策划起草",
    r"策划修订": "策划修订",
    r"监察审核": "监察审核",
    r"调度派遣": "调度派遣",
    r"已派遣": "已派遣",
    r"小队执行": "小队执行",
    r"汇总回报": "汇总回报",
    # UI 文本
    r"委托看板": "委托看板",
    r"战报阁": "战报阁",
    r"委托库": "委托库",
    r"任务模板": "任务模板",
    r"发布委托": "发布委托",
    r"团长视角": "团长视角",
    r"实时委托追踪": "实时委托追踪",
    r"QuestBoard 控制台": "QuestBoard 控制台",
    r"有委托请下达，无事解散": "有委托请下达，无事解散",
    r"副团长调度": "副团长调度",
    r"副团长巡检": "副团长巡检",
}

# 文件类型处理
TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".json",
    ".html",
    ".ts",
    ".tsx",
    ".sh",
    ".yml",
    ".yaml",
    ".txt",
}


def should_process_file(filepath):
    """判断是否应该处理该文件"""
    if filepath.suffix not in TEXT_EXTENSIONS:
        return False
    # 跳过某些目录
    skip_dirs = [".git", ".superpowers", "__pycache__", ".ruff_cache", ".idea"]
    for skip in skip_dirs:
        if skip in str(filepath):
            return False
    return True


def replace_in_content(content):
    """在内容中执行所有替换"""
    result = content
    for pattern, replacement in REPLACEMENTS.items():
        result = re.sub(pattern, replacement, result)
    return result


def process_file(filepath):
    """处理单个文件"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = replace_in_content(content)

        if new_content != content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False


def main():
    """主函数"""
    processed = 0
    modified = 0

    # 遍历所有文件
    for filepath in BASE.rglob("*"):
        if filepath.is_file() and should_process_file(filepath):
            processed += 1
            if process_file(filepath):
                modified += 1
                print(f"✓ {filepath.relative_to(BASE)}")

    print(f"\n处理完成: {processed} 个文件, {modified} 个文件被修改")


if __name__ == "__main__":
    main()
