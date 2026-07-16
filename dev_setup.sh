#!/bin/bash

# TerraMow 开发环境设置脚本

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 使用相对路径设置路径变量
HA_CORE_PATH="$SCRIPT_DIR/../HomeAssistantTest/ha_core"
TERRAMOW_PATH="$SCRIPT_DIR"

echo "设置 TerraMow 开发环境..."

# 1. 检查 HA 核心是否存在
if [ ! -d "$HA_CORE_PATH" ]; then
    echo "错误: Home Assistant 核心目录不存在: $HA_CORE_PATH"
    exit 1
fi

# 2. 创建符号链接 (如果不存在)
CUSTOM_COMPONENTS_DIR="$HA_CORE_PATH/config/custom_components"
TERRAMOW_LINK="$CUSTOM_COMPONENTS_DIR/terramow_ce"

if [ ! -L "$TERRAMOW_LINK" ]; then
    echo "创建符号链接..."
    mkdir -p "$CUSTOM_COMPONENTS_DIR"
    ln -sf "$TERRAMOW_PATH/custom_components/terramow_ce" "$TERRAMOW_LINK"
    echo "✅ 符号链接已创建: $TERRAMOW_LINK"
else
    echo "✅ 符号链接已存在"
fi

# 3. 设置 Python 虚拟环境
if [ ! -d "$HA_CORE_PATH/venv" ]; then
    echo "创建虚拟环境..."
    cd "$HA_CORE_PATH"
    python3 -m venv venv
    source venv/bin/activate
    pip install -e .
    pip install -r requirements_dev.txt
    echo "✅ 虚拟环境已创建"
else
    echo "✅ 虚拟环境已存在"
fi

# 4. 安装开发依赖
echo "安装 TerraMow 开发依赖..."
cd "$TERRAMOW_PATH"
if [ -f "pyproject.toml" ]; then
    source "$HA_CORE_PATH/venv/bin/activate"
    pip install -e ".[dev]"
    echo "✅ 开发依赖已安装"
fi

echo "🎉 开发环境设置完成!"
echo ""
echo "使用方法:"
echo "1. 启动 Home Assistant: cd $HA_CORE_PATH && source venv/bin/activate && python -m homeassistant --config config"
echo "2. 或在 VS Code 中使用调试配置启动"
echo "3. 运行测试: pytest tests/components/terramow_ce/ -v"