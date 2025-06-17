# Galgame 插件配置说明

本文档说明了Galgame插件的配置参数。配置文件位于 `config.json`。

## 基本配置

- `similarity`: 模糊搜索相似度阈值 (0-100)
- `cache_dir`: 缓存目录路径（相对于数据目录）
- `token_refresh_interval`: token刷新间隔（分钟）
- `max_retries`: API请求最大重试次数

## API配置

```json
"api": {
    "base_url": "API基础URL",
    "timeout": "请求超时时间（秒）",
    "user_agent": "请求User-Agent"
}
```

## 图片配置

```json
"image": {
    "max_size_bytes": "最大图片大小（字节）",
    "formats": "支持的图片格式列表",
    "default_format": "默认图片格式"
}
```

## 搜索配置

```json
"search": {
    "max_results": "最大结果数",
    "min_similarity": "最小相似度",
    "fuzzy_timeout": "模糊搜索超时时间（秒）"
}
```

## 缓存配置

```json
"cache": {
    "image_max_age_days": "图片缓存最大保存天数",
    "image_max_size_mb": "图片缓存最大大小（MB）",
    "api_ttl_seconds": "API响应缓存生存时间（秒）",
    "api_max_entries": "API缓存最大条目数"
}
```

## 命令冷却配置

```json
"cooldown": {
    "search": {
        "rate": "单位时间内允许的请求次数",
        "per": "时间单位（秒）"
    },
    "fuzzy": {
        "rate": "单位时间内允许的请求次数",
        "per": "时间单位（秒）"
    },
    "info": {
        "rate": "单位时间内允许的请求次数",
        "per": "时间单位（秒）"
    }
}
```

## 目录结构

```
data/galgame/
├── config.json    # 配置文件
├── README.md      # 本文档
└── cache/         # 缓存目录
    └── images/    # 图片缓存
```

## 环境变量

以下配置项可以通过环境变量覆盖：

- `GALGAME_CACHE_DIR`: 缓存目录路径
- `GALGAME_API_BASE_URL`: API基础URL
- `GALGAME_API_TIMEOUT`: API超时时间
- `GALGAME_IMAGE_MAX_SIZE`: 最大图片大小
- `GALGAME_CACHE_MAX_SIZE`: 缓存最大大小

环境变量优先级高于配置文件。

## 注意事项

1. 所有路径都相对于数据目录（`data/galgame/`）
2. 图片缓存超过最大大小时，将自动清理最旧的文件
3. API响应缓存超过最大条目数时，将自动清理最旧的条目
4. 命令冷却时间针对每个用户单独计算 