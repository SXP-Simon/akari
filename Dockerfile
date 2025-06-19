# 使用官方 uv Python 镜像
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# 构建参数
ARG INCLUDE_MEME=false
ARG BAIDU_TRANS_APPID=""
ARG BAIDU_TRANS_APIKEY=""
ENV BAIDU_TRANS_APPID=${BAIDU_TRANS_APPID}
ENV BAIDU_TRANS_APIKEY=${BAIDU_TRANS_APIKEY}

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 安装字体（用于 meme 生成器）
RUN if [ "$INCLUDE_MEME" = "true" ]; then \
        apt-get update && apt-get install -y \
        fonts-noto-color-emoji \
        libegl1 \
        libgl1-mesa-glx \
        libgles2 \
        fontconfig \
        wget \
        && rm -rf /var/lib/apt/lists/*; \
    fi

# 复制项目配置文件
COPY pyproject.toml ./
COPY README.md ./
COPY LICENSE ./

# 创建虚拟环境并安装依赖
RUN uv venv && \
    uv pip install -e . && \
    if [ "$INCLUDE_MEME" != "true" ]; then \
        uv pip uninstall meme-generator; \
    fi

# 复制源代码
COPY akari/ ./akari/

# 如果不需要 meme 功能，删除 meme 插件
RUN if [ "$INCLUDE_MEME" != "true" ]; then \
        rm -rf ./akari/plugins/meme/; \
    fi

# 创建数据目录
RUN mkdir -p /app/data

# 复制数据文件
COPY data/ ./data/

# 如果不需要 meme 功能，删除 meme 数据
RUN if [ "$INCLUDE_MEME" != "true" ]; then \
        rm -rf ./data/meme/; \
    fi

# 安装 meme 生成器字体（仅当包含 meme 功能时）
RUN if [ "$INCLUDE_MEME" = "true" ]; then \
        mkdir -p /usr/share/fonts/meme-fonts && \
        cd /usr/share/fonts/meme-fonts && \
        # 下载所有必要的字体文件
        wget -O consola.ttf "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/consola.ttf" && \
        wget -O FZKATJW.ttf "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/FZKATJW.ttf" && \
        wget -O FZXS14.ttf "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/FZXS14.ttf" && \
        wget -O FZSJ-QINGCRJ.ttf "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/FZSJ-QINGCRJ.ttf" && \
        wget -O FZSEJW.ttf "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/FZSEJW.ttf" && \
        wget -O NotoSansSC-Regular.ttf "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/NotoSansSC-Regular.ttf" && \
        wget -O NotoSerifSC-Regular.otf "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/NotoSerifSC-Regular.otf" && \
        wget -O "HiraginoMin-W5-90-RKSJ-H-2.ttc" "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/HiraginoMin-W5-90-RKSJ-H-2.ttc" && \
        wget -O "Aller_Bd.ttf" "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/Aller%5FBd.ttf" && \
        wget -O "RoGSanSrfStd-Bd.otf" "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/RoGSanSrfStd-Bd.otf" && \
        wget -O "GlowSansSC-Normal-Heavy.otf" "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/GlowSansSC-Normal-Heavy.otf" && \
        wget -O "庞门正道粗书体.ttf" "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/%E5%BA%9E%E9%97%A8%E6%AD%A3%E9%81%93%E7%B2%97%E4%B9%A6%E4%BD%93.ttf" && \
        wget -O "Neo Sans Bold.ttf" "https://raw.githubusercontent.com/MemeCrafters/meme-generator/main/resources/fonts/Neo%20Sans%20Bold.ttf" && \
        # 建立字体缓存
        fc-cache -fv; \
    fi

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash akari

# 仅在包含 meme 功能时，写入 meme-generator 默认配置文件
RUN [ "$INCLUDE_MEME" = "true" ] && mkdir -p /home/akari/.config/meme_generator && cat > /home/akari/.config/meme_generator/config.toml <<EOF
[meme]
load_builtin_memes = true  # 是否加载内置表情包
meme_dirs = []
meme_disabled_list = []

[resource]
resource_urls = [
  "https://raw.githubusercontent.com/MemeCrafters/meme-generator/",
  "https://mirror.ghproxy.com/https://raw.githubusercontent.com/MemeCrafters/meme-generator/",
  "https://cdn.jsdelivr.net/gh/MemeCrafters/meme-generator@",
  "https://fastly.jsdelivr.net/gh/MemeCrafters/meme-generator@",
  "https://raw.gitmirror.com/MemeCrafters/meme-generator/"
]

[gif]
gif_max_size = 10.0
gif_max_frames = 100

[translate]
baidu_trans_appid = "${BAIDU_TRANS_APPID}"  # 可通过构建参数或环境变量传入
baidu_trans_apikey = "${BAIDU_TRANS_APIKEY}"  # 可通过构建参数或环境变量传入

[server]
host = "127.0.0.1"
port = 2233

[log]
log_level = "INFO"
EOF
RUN [ "$INCLUDE_MEME" = "true" ] && chown -R akari:akari /home/akari/.config
RUN chown -R akari:akari /app
USER akari

# 下载 meme 生成器图片资源（仅当包含 meme 功能时，akari 用户身份）
RUN if [ "$INCLUDE_MEME" = "true" ]; then \
    uv run meme download; \
fi

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# 启动命令
CMD ["uv", "run", "akari"]