import os
import asyncio
import shutil
import logging
import datetime
import time
import jmcomic
import discord # Import discord
import zipfile # Import zipfile

class MangaDownloaderService:
    def __init__(self, option, client, download_dir, logger):
        self.option = option
        self.client = client
        self.download_dir = download_dir
        self.logger = logger
        
    async def _download_album(self, album_id):
        """下载整本漫画"""
        if not self.option or not self.client:
            self.logger.error("JM选项初始化失败，无法下载")
            return None
            
        try:
            # 获取漫画信息
            album_detail = self.client.get_album_detail(album_id)
            
            # 下载漫画
            self.logger.info(f"开始下载漫画: {album_id}")
            await asyncio.to_thread(jmcomic.download_album, album_id, self.option)
            
            # 获取所有章节详情
            all_photos = []
            for photo in album_detail:
                photo_detail = await asyncio.to_thread(self.client.get_photo_detail, photo.photo_id)
                if photo_detail:
                    all_photos.append(photo_detail)
                    
            return album_detail, all_photos
            
        except Exception as e:
            self.logger.error(f"下载漫画 {album_id} 时出错: {e}")
            return None
    
    async def _download_photo(self, photo_id):
        """下载单个章节"""
        if not self.option or not self.client:
            self.logger.error("JM选项初始化失败，无法下载")
            return None
            
        try:
            # 获取章节信息
            photo_detail = await asyncio.to_thread(self.client.get_photo_detail, photo_id)
            
            # 下载章节所有图片
            self.logger.info(f"开始下载章节: {photo_id}")
            await asyncio.to_thread(jmcomic.download_photo, photo_id, self.option)
            
            return photo_detail
        except Exception as e:
            self.logger.error(f"下载章节 {photo_id} 时出错: {e}")
            return None

    async def _zip_directory(self, source_dir, output_zip_path):
        """异步地将指定目录压缩为ZIP文件"""
        try:
            await asyncio.to_thread(lambda: shutil.make_archive(output_zip_path.replace('.zip', ''), 'zip', source_dir))
            return True
        except Exception as e:
            self.logger.error(f"压缩目录 {source_dir} 到 {output_zip_path} 时出错: {e}")
            return False

    async def send_album_images(self, ctx, album_id, album_name=None):
        """
        将指定漫画ID下的所有图片压缩成多个ZIP文件并发送，每个文件不超过10MB
        """
        album_base_dir = os.path.join(self.download_dir, str(album_id))
        
        if not os.path.exists(album_base_dir):
            self.logger.warning(f"漫画目录不存在: {album_base_dir}")
            await ctx.send(f"漫画《{album_name or album_id}》下载完成，但目录 `{album_id}` 不存在。")
            return
            
        # Send title as a plain message or embed
        if album_name:
            await ctx.send(f"**漫画《{album_name}》**")

        embed_zipping = discord.Embed(
            title="📦 正在打包漫画",
            description=f"正在将漫画《{album_name or album_id}》打包成多个ZIP文件，请稍候...",
            color=discord.Color.blue()
        )
        message = await ctx.send(embed=embed_zipping)

        try:
            all_image_paths = self._get_all_image_paths_in_album_dir(album_id)
            if not all_image_paths:
                await message.edit(embed=discord.Embed(
                    title="❌ 打包失败",
                    description="漫画目录中没有找到图片，无法打包。",
                    color=discord.Color.red()
                ))
                return

            max_zip_size = 10 * 1024 * 1024  # 10MB in bytes
            current_zip_files = []
            current_zip_size = 0
            part_number = 1
            zip_files_to_send = []

            for img_path in all_image_paths:
                img_size = os.path.getsize(img_path)

                if current_zip_size + img_size > max_zip_size and current_zip_files:
                    # Current ZIP is full, create a new one
                    zip_filename = f"{album_name or album_id}_part{part_number}.zip"
                    zip_filepath = os.path.join(self.download_dir, zip_filename)
                    
                    # Create ZIP synchronously to allow better control over content
                    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for file_to_zip in current_zip_files:
                            arcname = os.path.relpath(file_to_zip, album_base_dir) # Relative path inside zip
                            zf.write(file_to_zip, arcname)

                    zip_files_to_send.append(zip_filepath)
                    current_zip_files = []
                    current_zip_size = 0
                    part_number += 1

                current_zip_files.append(img_path)
                current_zip_size += img_size
            
            # Add any remaining files to the last zip
            if current_zip_files:
                zip_filename = f"{album_name or album_id}_part{part_number}.zip"
                zip_filepath = os.path.join(self.download_dir, zip_filename)

                with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for file_to_zip in current_zip_files:
                        arcname = os.path.relpath(file_to_zip, album_base_dir)
                        zf.write(file_to_zip, arcname)
                zip_files_to_send.append(zip_filepath)

            if not zip_files_to_send:
                await message.edit(embed=discord.Embed(
                    title="❌ 打包失败",
                    description="未能创建任何ZIP文件，请检查漫画内容。",
                    color=discord.Color.red()
                ))
                return

            embed_sending = discord.Embed(
                title="📤 正在发送漫画",
                description=f"漫画《{album_name or album_id}》已打包成 {len(zip_files_to_send)} 个ZIP文件，正在发送...",
                color=discord.Color.green()
            )
            await message.edit(embed=embed_sending)
            
            # 发送所有ZIP文件
            for i, filepath in enumerate(zip_files_to_send):
                filename = os.path.basename(filepath)
                await ctx.send(f"发送第 {i+1}/{len(zip_files_to_send)} 部分: **{filename}**", file=discord.File(filepath, filename=filename))
                await asyncio.sleep(1) # Small delay between sending multiple files

            embed_success = discord.Embed(
                title="✅ 发送完成",
                description=f"漫画《{album_name or album_id}》的所有ZIP文件已成功发送。",
                color=discord.Color.green()
            )
            await message.edit(embed=embed_success)

        except Exception as e:
            self.logger.error(f"发送漫画 {album_id} 的ZIP文件时出错: {e}")
            await message.edit(embed=discord.Embed(
                title="⚠️ 操作出错",
                description=f"发送漫画《{album_name or album_id}》的ZIP文件时出错: {str(e)}",
                color=discord.Color.red()
            ))
        finally:
            # 清理所有生成的ZIP文件
            for filepath in zip_files_to_send:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    self.logger.info(f"已删除临时ZIP文件: {filepath}")

    async def send_photo_images(self, ctx, photo, title=None):
        """以转发消息的形式发送章节的所有图片"""
        try:
            if title is None:
                title = ""
            
            photo_dir = os.path.join(self.download_dir, str(photo.album_id), str(photo.photo_id))
            
            if not os.path.exists(photo_dir):
                self.logger.info(f"尝试使用备用目录结构: {photo_dir}不存在，尝试直接使用album_id目录")
                photo_dir = os.path.join(self.download_dir, str(photo.album_id))
                
                if not os.path.exists(photo_dir):
                    self.logger.error(f"所有可能的章节目录都不存在: {photo_dir}")
                    return
                
            self.logger.info(f"使用目录: {photo_dir}来获取图片")
                
            image_files = sorted([f for f in os.listdir(photo_dir) if f.endswith(('.jpg', '.png', '.webp', '.jpeg'))])
            if not image_files:
                self.logger.error(f"章节目录中没有找到图片: {photo_dir}")
                return
            
            self.logger.info(f"在{photo_dir}中找到{len(image_files)}张图片")
            
            # Send title as a plain message or embed
            if title:
                await ctx.send(f"**{title}**")

            # Send images in batches
            batch_size = 10 # Discord attachment limit per message
            for i in range(0, len(image_files), batch_size):
                batch_files = image_files[i:i+batch_size]
                files_to_send = [discord.File(os.path.join(photo_dir, img_file)) for img_file in batch_files]
                await ctx.send(files=files_to_send)
                await asyncio.sleep(0.5) # Small delay to avoid rate limits
                    
        except Exception as e:
            self.logger.error(f"发送章节图片时出错: {e}")

    def _get_all_image_paths_in_album_dir(self, album_id):
        """递归获取指定漫画ID目录下所有图片文件的路径"""
        all_image_files = []
        album_base_dir = os.path.join(self.download_dir, str(album_id))
        
        if not os.path.exists(album_base_dir):
            self.logger.warning(f"漫画目录不存在: {album_base_dir}")
            return []

        for dirpath, dirnames, filenames in os.walk(album_base_dir):
            for filename in filenames:
                if filename.lower().endswith(('.jpg', '.png', '.webp', '.jpeg')):
                    all_image_files.append(os.path.join(dirpath, filename))
        return sorted(all_image_files)

    def _get_dir_size(self, path):
        """获取目录大小（字节）"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                total_size += os.path.getsize(file_path)
        return total_size
    
    async def cleanup_comic_files(self):
        """清理下载目录中的漫画文件"""
        try:
            if os.path.exists(self.download_dir):
                self.logger.info(f"开始执行每日漫画文件清理: {self.download_dir}")
                
                # 统计清理前的文件数量和大小
                total_size_before = self._get_dir_size(self.download_dir)
                
                # 执行清理操作
                shutil.rmtree(self.download_dir)
                os.makedirs(self.download_dir, exist_ok=True)
                
                self.logger.info(f"漫画文件清理完成，释放了 {total_size_before / (1024*1024):.2f} MB 空间")
                return True
        except Exception as e:
            self.logger.error(f"清理漫画文件时出错: {e}")
            return False

    async def start_cleanup_scheduler(self):
        """启动定时清理任务"""
        while True:
            try:
                # 计算距离下一个凌晨3点的时间
                now = datetime.datetime.now()
                next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if now >= next_run:
                    # 如果当前时间已经过了今天的3点，计算到明天3点的时间
                    next_run = next_run + datetime.timedelta(days=1)
                
                # 计算等待时间
                wait_seconds = (next_run - now).total_seconds()
                self.logger.info(f"下一次漫画文件清理将在 {next_run.strftime('%Y-%m-%d %H:%M:%S')} 进行，等待 {wait_seconds:.2f} 秒")
                
                # 等待到指定时间
                await asyncio.sleep(wait_seconds)
                
                # 执行清理
                await self.cleanup_comic_files()
                
                # 等待一小段时间，避免连续执行
                await asyncio.sleep(60)
            except Exception as e:
                self.logger.error(f"定时清理任务出错: {e}")
                # 如果出错，等待一段时间后重试
                await asyncio.sleep(3600)  # 1小时后重试