# Docker 部署指南

本文档介绍如何使用 Docker 部署 Akari Discord Bot。

## 快速开始

### 1. 克隆项目

```bash
git clone <仓库地址>
cd akari
```

### 2. 构建并启动

#### 不包含 meme 功能（默认）

```bash
# 构建镜像（不包含 meme 功能）
docker build -t akari-bot .

# 运行容器
docker run -d \
  --name akari-bot \
  --restart unless-stopped \
  -e DISCORD_BOT_TOKEN=你的令牌 \
  -e GOOGLE_AI_KEY=你的API密钥 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  akari-bot
```

#### 包含 meme 功能

```bash
# 构建镜像（包含 meme 功能）
# 如需百度翻译功能，可传递 BAIDU_TRANS_APPID 和 BAIDU_TRANS_APIKEY
# 可在 百度翻译开放平台 (http://api.fanyi.baidu.com) 申请
docker build --build-arg INCLUDE_MEME=true --build-arg BAIDU_TRANS_APPID=你的appid --build-arg BAIDU_TRANS_APIKEY=你的apikey -t akari-bot .


# 运行容器
docker run -d \
  --name akari-bot \
  --restart unless-stopped \
  -e DISCORD_BOT_TOKEN=你的令牌 \
  -e GOOGLE_AI_KEY=你的API密钥 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  akari-bot
```

> 如需百度翻译相关表情包功能，请务必传递 `BAIDU_TRANS_APPID` 和 `BAIDU_TRANS_APIKEY`，否则相关功能不可用。

## 日志查看

```bash
# 查看实时日志
docker logs -f akari-bot
```

## 数据

Docker 配置会自动将以下目录挂载到宿主机：

- `./data` → `/app/data` - 机器人数据文件
- `./logs` → `/app/logs` - 日志文件

## 环境变量

| 变量名 | 必需 | 说明 |
|--------|------|------|
| `DISCORD_BOT_TOKEN` | 是 | Discord 机器人令牌 |
| `GOOGLE_AI_KEY` | 是 | Google AI API 密钥 |

## Windows 环境变量传递

在 Windows 下，可以使用以下命令传递环境变量：

### PowerShell
```powershell
docker run -d `
  --name akari-bot `
  --restart unless-stopped `
  -e DISCORD_BOT_TOKEN="你的令牌" `
  -e GOOGLE_AI_KEY="你的API密钥" `
  -v ${PWD}/data:/app/data `
  -v ${PWD}/logs:/app/logs `
  akari-bot
```

### CMD
```cmd
docker run -d ^
  --name akari-bot ^
  --restart unless-stopped ^
  -e DISCORD_BOT_TOKEN=你的令牌 ^
  -e GOOGLE_AI_KEY=你的API密钥 ^
  -v %cd%/data:/app/data ^
  -v %cd%/logs:/app/logs ^
  akari-bot
```

### 使用 .env 文件
创建 `.env` 文件：
```env
DISCORD_BOT_TOKEN=你的令牌
GOOGLE_AI_KEY=你的API密钥
```

然后使用：
```bash
docker run -d \
  --name akari-bot \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  akari-bot
```

