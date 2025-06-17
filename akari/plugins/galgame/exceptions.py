"""异常模块

本模块定义了插件使用的异常类。

Classes:
    GalGameError: 基础异常类
    APIError: API异常
    NoGameFound: 游戏未找到异常
    ImageError: 图片处理异常
    ConfigError: 配置异常
"""

from typing import Optional

class GalGameError(Exception):
    """Galgame插件基础异常类"""
    pass

class APIError(GalGameError):
    """API异常
    
    Attributes:
        message: 错误信息
        code: 错误代码
    """
    def __init__(self, message: str, code: int = None) -> None:
        self.message = message
        self.code = code
        super().__init__(message)

class NoGameFound(GalGameError):
    """游戏未找到异常"""
    pass

class ImageError(GalGameError):
    """图片处理异常"""
    pass

class ConfigError(GalGameError):
    """配置异常"""
    pass

class GalGameError(Exception):
    """Galgame插件基础异常类"""
    
    def __init__(self, message: str, cause: Optional[Exception] = None) -> None:
        """初始化异常
        
        Args:
            message: 错误消息
            cause: 导致此异常的原始异常
        """
        super().__init__(message)
        self.cause = cause
        
    def __str__(self) -> str:
        if self.cause:
            return f"{super().__str__()}\n原因: {str(self.cause)}"
        return super().__str__()
        
class APIError(GalGameError):
    """API相关异常
    
    Attributes:
        code: API错误代码
        message: 错误消息
    """
    
    def __init__(self, message: str, code: int = -1) -> None:
        """初始化异常
        
        Args:
            message: 错误消息
            code: API错误代码
        """
        super().__init__(message)
        self.code = code
        
    def __str__(self) -> str:
        return f"API错误 (代码: {self.code}): {super().__str__()}"
        
class NoGameFound(GalGameError):
    """游戏未找到异常"""
    pass
    
class ImageError(GalGameError):
    """图片处理异常
    
    Attributes:
        url: 相关图片URL
    """
    
    def __init__(self, message: str, url: Optional[str] = None) -> None:
        """初始化异常
        
        Args:
            message: 错误消息
            url: 相关图片URL
        """
        super().__init__(message)
        self.url = url
        
    def __str__(self) -> str:
        if self.url:
            return f"图片处理错误 ({self.url}): {super().__str__()}"
        return f"图片处理错误: {super().__str__()}"
        
class ConfigError(GalGameError):
    """配置相关异常
    
    Attributes:
        key: 相关配置键
    """
    
    def __init__(self, message: str, key: Optional[str] = None) -> None:
        """初始化异常
        
        Args:
            message: 错误消息
            key: 相关配置键
        """
        super().__init__(message)
        self.key = key
        
    def __str__(self) -> str:
        if self.key:
            return f"配置错误 ({self.key}): {super().__str__()}"
        return f"配置错误: {super().__str__()}" 