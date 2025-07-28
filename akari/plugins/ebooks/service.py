import os
import aiohttp
from typing import List, Optional
from akari.bot.services.base import BaseService
from .config import EbooksConfig
from .models import SearchResult, Download, URL, FileInfo
from .zlibrary_client import Zlibrary
from .annas_py.extractors.search import search as annas_search
from .annas_py.extractors.download import get_information as annas_download

class EbooksService(BaseService):
    """
    电子书服务实现，统一 ebooks 命令分发多平台
    """
    def __init__(self, bot, config: Optional[EbooksConfig] = None):
        super().__init__(bot, config or EbooksConfig())
        self._config: EbooksConfig = self._config or EbooksConfig()
        self.proxy = os.environ.get("https_proxy")
        self.zlib_client = Zlibrary(
            email=self._config.zlib_email,
            password=self._config.zlib_password
        )

    async def search_ebooks(self, query: str, tag: str = None, limit: int = 20) -> List[SearchResult]:
        """
        多平台综合搜索，支持 tag
        """
        results = []
        # Z-Library
        zlib_query = f"{query} {tag}" if tag else query
        if self._config.enable_zlib:
            try:
                zlib_data = self.zlib_client.search(message=zlib_query, limit=limit)
                for item in zlib_data.get("books", []):
                    print(f"搜索结果书籍 ID: {item.get('id', '')}, HashID: {item.get('hash', '')}")
                    hashid = item.get('hash', None)
                    if not hashid:
                        print(f"警告: 搜索结果书籍 ID {item.get('id', '')} 缺少 HashID。")
                    results.append(SearchResult(
                        id=item.get("id", ""),
                        title=item.get("title", "未知标题"),
                        authors=", ".join(item.get("authors", [])),
                        file_info=FileInfo(
                            extension=item.get("extension", "未知"),
                            size=item.get("filesize", "未知"),
                            language=item.get("language"),
                            library="Z-Library"
                        ),
                        thumbnail=item.get("coverurl"),
                        publisher=item.get("publisher"),
                        publish_date=item.get("year"),
                        # hash 字段可补充
                        # description 字段可补充
                    ))
            except Exception as e:
                pass
        # Anna's Archive
        try:
            annas_results = annas_search(query, tag=tag) if tag else annas_search(query)
            results.extend(annas_results[:limit])
        except Exception as e:
            pass
        return results[:limit]

    async def download_ebooks(self, book_id: str, source: str = "zlib", hashid: str = None) -> Optional[Download]:
        """
        多平台下载，source 指定平台
        """
        temp_dir = "data/ebooks"  # 更改临时文件夹路径
        os.makedirs(temp_dir, exist_ok=True)  # 确保目录存在

        if source == "zlib":
            try:
                # 获取书籍信息
                book_info = self.zlib_client.getBookInfo(book_id, hashid)
                if not book_info:
                    print("获取书籍信息失败，API返回数据:", book_info)
                    return None

                # 下载文件
                file_data = None
                # 如果 HashID 缺失，尝试仅使用书籍 ID 下载文件
                if not hashid:
                    print(f"警告: HashID 缺失，尝试仅使用书籍 ID {book_id} 下载文件。")
                    file_data = self.zlib_client.__getBookFile(book_id, "")
                else:
                    file_data = self.zlib_client.__getBookFile(book_id, hashid)
                
                if not file_data:
                    print("下载文件失败，API返回数据:", file_data)
                    return None

                # 从文件数据中提取文件名
                file_name = file_data[0] if file_data else "未知文件名"
                file_path = os.path.join(temp_dir, file_name)

                # 保存文件到临时目录
                with open(file_path, "wb") as f:
                    f.write(file_data[1])

                # 返回下载信息
                return Download(
                    title=book_info.get("title", "未知标题"),
                    description=book_info.get("description", ""),
                    authors=", ".join(book_info.get("authors", [])),
                    file_info=FileInfo(
                        extension=book_info.get("extension", "未知"),
                        size=book_info.get("filesize", "未知"),
                        language=book_info.get("language"),
                        library="Z-Library"
                    ),
                    urls=[URL(title="下载链接", url=book_info.get("downloadUrl", ""))],
                    thumbnail=book_info.get("coverurl"),
                    publisher=book_info.get("publisher"),
                    publish_date=book_info.get("year"),
                    file_path=file_path
                )
            except Exception as e:
                print(f"下载失败: {e}")
                print(f"书籍 ID: {book_id}, 来源: {source}, HashID: {hashid}")
                return None
            finally:
                # 垃圾回收逻辑
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
        elif source == "annas":
            try:
                return annas_download(book_id)
            except Exception as e:
                print(f"下载失败: {e}")
                print(f"书籍 ID: {book_id}, 来源: {source}, HashID: {hashid}")
                return None
        return None
