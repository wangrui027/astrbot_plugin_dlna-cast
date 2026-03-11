import inspect
import os

from astrbot.api import logger  # 使用 astrbot 提供的 logger 接口
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

from .ctr.db_utils import DatabaseManager
from .ctr.webdav_ctr import WebDAVManager, WebDAVConfig

COMMAND_DLNA_CAST = "dlna-cast"

# 安全字段过滤
SENSITIVE_FIELDS = {'password', 'token', 'secret', 'api_key', 'auth'}


def build_params_dict(func_name, args, kwargs, func_code):
    """
    将函数参数组装成字典，自动过滤敏感信息

    Args:
        func_name: 函数名
        args: 位置参数元组
        kwargs: 关键字参数字典
        func_code: 函数的 __code__ 对象，用于获取参数名

    Returns:
        dict: 参数字典，敏感字段会被替换为 "***"
    """
    # 获取函数参数名列表（排除 self）
    arg_names = func_code.co_varnames[1:func_code.co_argcount]  # 跳过 self

    params = {}

    # 处理位置参数
    for i, arg in enumerate(args):
        if i < len(arg_names):
            name = arg_names[i]
            params[name] = "***" if name in SENSITIVE_FIELDS else arg

    # 处理关键字参数
    for name, value in kwargs.items():
        params[name] = "***" if name in SENSITIVE_FIELDS else value

    # 处理默认参数（未传入的）
    # 可以在这里补充默认值，如果需要的话

    return params


class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 获取当前插件所在目录
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        # 初始化数据库
        db_path = os.path.join(self.plugin_dir, 'data/plugin_data', 'data.db')
        self.db = DatabaseManager(db_path)
        # 初始化WebDAV管理器
        self.webdav_manager = WebDAVManager(self.db)
        logger.info(f"数据库初始化成功: {db_path}")

    @filter.command_group(COMMAND_DLNA_CAST)
    def dlna_cast(self, event: AstrMessageEvent):
        pass

    @dlna_cast.command("help")
    async def dlna_cast_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        logger.info("触发 /dlna-cast help 指令")
        self.db.log_message(event, inspect.currentframe().f_code.co_name)
        help_path = os.path.join(self.plugin_dir, 'help', 'base_help.md')
        try:
            with open(help_path, 'r', encoding='utf-8') as file:
                help_md = file.read()
            yield event.plain_result(help_md)
        except FileNotFoundError:
            logger.error(f"帮助文件未找到: {help_path}")
            yield event.plain_result("帮助文件不存在，请检查插件安装")

    @dlna_cast.group("webdav")
    def webdav(self, event: AstrMessageEvent):
        pass

    @webdav.command("help")
    async def webdav_help(self, event: AstrMessageEvent):
        """webdav 指令帮助"""
        logger.info("触发 /dlna-cast webdav help 指令")
        self.db.log_message(event, inspect.currentframe().f_code.co_name)

        # 获取当前选中的服务器信息
        success, msg, selected = self.webdav_manager.get_current_selected()
        selected_info = f"\n✅ 当前选中：**{selected['name']}**" if success else "\n⚠️ 当前未选中任何服务器"

        help_text = f"""
### 📚 WebDAV 指令帮助：

1️⃣ `/dlna-cast` `webdav` `help`
    显示本帮助信息

2️⃣ `/dlna-cast` `webdav` `add` `<名称>` `<URL>` `[用户名]` `[密码]`
    添加WebDAV服务器配置（第一个添加的会自动选中）
    📝 示例：`/dlna-cast` `webdav` `add` `我的NAS` `http://192.168.1.100:5005/webdav` `admin` `123456`

3️⃣ `/dlna-cast` `webdav` `ls`

4️⃣ `/dlna-cast` `webdav` `select` `<序号>`
    选中指定序号的WebDAV服务器（用于后续浏览操作）
    📝 示例：`/dlna-cast` `webdav` `select` `1`

5️⃣ `/dlna-cast` `webdav` `rm` `<序号>`
    删除指定序号的WebDAV服务器配置
    📝 示例：`/dlna-cast` `webdav` `rm` `2`

6️⃣ `/dlna-cast` `webdav` `browse` [路径]
    浏览当前选中服务器的资源（默认根目录）
    📝 示例：`/dlna-cast` `webdav` `browse` `/movies`

{'-'*40}
### 📌 路径使用说明：

1️⃣ 简单路径（无空格）：
   ✅ `/dlna-cast` `webdav` `browse` `/movies/action`

2️⃣ 包含空格的路径（无需引号！）：
   ✅ `/dlna-cast` `webdav` `browse` `/天翼云盘/凡人修仙传 1-124集`

3️⃣ 特殊路径：
   • 根目录：`/dlna-cast` `webdav` `browse` `/`
   • 上级目录：`/dlna-cast` `webdav` `browse` `..`

{'-'*40}
### 🎯 常用操作示例：

1. 添加服务器后自动选中，直接浏览：
   `/dlna-cast` `webdav` `browse` `/`

2. 进入子目录（直接输入完整路径）：
   `/dlna-cast` `webdav` `browse` `/天翼云盘/凡人修仙传 1-124集`

3. 返回上级：
   `/dlna-cast` `webdav` `browse` `..`

4. 播放视频（使用完整路径）：
   `/dlna-cast` `play` `/天翼云盘/凡人修仙传 1-124集/第001集.mp4`

{selected_info}
    """
        yield event.plain_result(help_text.strip())

    @webdav.command("add")
    async def webdav_add(self, event: AstrMessageEvent, name: str, url: str, username: str = None,
                         password: str = None):
        """webdav 服务器添加"""
        logger.info("触发 /dlna-cast webdav add 指令")

        # 记录参数
        params_dict = {
            'name': name,
            'url': url,
            'username': username,
            'password': password
        }

        try:
            # 创建配置对象
            config = WebDAVConfig.from_url(name, url, username, password)

            # 添加配置
            success, message, saved_config = self.webdav_manager.add_config(config)

            if success:
                result = f"✅ WebDAV服务【{name}】添加成功"
                result += f"\n服务器: {config.url}"
                result += f"\n用户名: {config.username or '无'}"
                if saved_config and saved_config.is_selected:
                    result += f"\n\n✨ 这是第一个添加的服务器，已自动选中"
            else:
                result = f"❌ WebDAV服务添加失败: {message}"

        except Exception as e:
            logger.error(f"webdav_add 异常: {e}")
            result = f"❌ 添加过程发生异常: {str(e)}"

        # 记录日志并返回结果
        self.db.log_message(event, inspect.currentframe().f_code.co_name, params_dict, result)
        yield event.plain_result(result)

    @webdav.command("ls")
    async def webdav_ls(self, event: AstrMessageEvent):
        """webdav 服务器列表查看"""
        logger.info("触发 /dlna-cast webdav ls 指令")
        self.db.log_message(event, inspect.currentframe().f_code.co_name)

        try:
            success, message, configs = self.webdav_manager.get_configs_list()

            if success:
                result = self.webdav_manager.format_config_list(configs)
                if configs:
                    result += "\n\n💡 使用 /dlna-cast webdav select <序号> 选中服务器进行浏览"
            else:
                result = f"❌ {message}"

        except Exception as e:
            logger.error(f"webdav_ls 异常: {e}")
            result = f"❌ 获取列表失败: {str(e)}"

        yield event.plain_result(result)

    @webdav.command("select")
    async def webdav_select(self, event: AstrMessageEvent, index: int):
        """webdav 服务器选中"""
        logger.info(f"触发 /dlna-cast webdav select 指令, index: {index}")

        params_dict = {'index': index}

        try:
            success, message, config = self.webdav_manager.select_config(index)

            if success and config:
                result = f"✅ {message}"
                result += f"\nURL: {config['url']}"
                result += f"\n用户名: {config.get('username', '无')}"
                result += "\n\n💡 现在可以使用以下命令："
                result += "\n• `/dlna-cast` `webdav` `browse` [路径] - 浏览资源"
                result += "\n• /dlna-cast webdav rm <序号> - 删除配置"
            else:
                result = f"❌ {message}"
                # 如果失败，显示当前可用列表
                _, _, configs = self.webdav_manager.get_configs_list()
                if configs:
                    result += f"\n\n当前可用配置：\n{self.webdav_manager.format_config_list(configs)}"

        except Exception as e:
            logger.error(f"webdav_select 异常: {e}")
            result = f"❌ 选中操作失败: {str(e)}"

        self.db.log_message(event, inspect.currentframe().f_code.co_name, params_dict, result)
        yield event.plain_result(result)

    @webdav.command("rm")
    async def webdav_rm(self, event: AstrMessageEvent, index: int):
        """webdav 服务器删除"""
        logger.info(f"触发 /dlna-cast webdav rm 指令, index: {index}")

        params_dict = {'index': index}

        try:
            success, message, deleted_config = self.webdav_manager.delete_config(index)

            if success and deleted_config:
                result = f"✅ {message}"
                # 如果删除的是选中的，提示新的选中状态
                if deleted_config['is_selected']:
                    _, _, new_selected = self.webdav_manager.get_current_selected()
                    if new_selected:
                        result += f"\n\n已自动切换到新服务器：【{new_selected['name']}】"
            else:
                result = f"❌ {message}"
                # 如果失败，显示当前可用列表
                _, _, configs = self.webdav_manager.get_configs_list()
                if configs:
                    result += f"\n\n当前可用配置：\n{self.webdav_manager.format_config_list(configs)}"

        except Exception as e:
            logger.error(f"webdav_rm 异常: {e}")
            result = f"❌ 删除操作失败: {str(e)}"

        self.db.log_message(event, inspect.currentframe().f_code.co_name, params_dict, result)
        yield event.plain_result(result)

    @webdav.command("browse")
    async def webdav_browse(self, event: AstrMessageEvent):
        """webdav 资源浏览"""

        # 获取指令后的路径，指令后的内容全部作为 path，空格也算，无需引号引起来
        path = event.message_str.replace(f"{COMMAND_DLNA_CAST} webdav browse ", "", 1)
        logger.info(f"触发 `/dlna-cast` `webdav` `browse` 指令, 原始路径: {path}")
        params_dict = {'path': path}

        try:
            # 处理路径参数
            browse_path = path.strip()

            # 如果路径为空，默认为根目录
            if not browse_path:
                browse_path = "/"
                logger.info("路径为空，使用根目录")
            else:
                # 如果路径被引号包裹，移除引号（兼容用户习惯）
                if (browse_path.startswith("'") and browse_path.endswith("'")) or \
                        (browse_path.startswith('"') and browse_path.endswith('"')):
                    browse_path = browse_path[1:-1]
                    logger.info(f"移除引号后: {browse_path}")

            # 从会话中获取当前路径（需要实现会话存储）
            # 这里简化处理，使用 event 的临时存储
            current_path = getattr(event, '_current_webdav_path', '/')
            logger.info(f"当前路径: {current_path}")

            # 调用管理器浏览路径，传入当前路径
            success, message, items, selected_config, new_path = self.webdav_manager.browse_path(
                browse_path,
                current_path
            )

            if not success:
                # 提供更友好的错误提示
                if "请先选中" in message:
                    _, _, configs = self.webdav_manager.get_configs_list()
                    if configs:
                        result = f"❌ {message}\n\n📋 可用服务器：\n{self.webdav_manager.format_config_list(configs)}"
                        result += "\n\n💡 使用 /dlna-cast webdav select <序号> 选中一个服务器"
                    else:
                        result = f"❌ {message}\n\n💡 使用 /dlna-cast webdav add 添加服务器"
                    yield event.plain_result(result)
                elif "404" in message or "Not Found" in message:
                    result = f"❌ 路径不存在：'{browse_path}'"
                    # 尝试提供父路径提示
                    parent_path = os.path.dirname(browse_path.rstrip('/'))
                    if parent_path and parent_path != browse_path:
                        result += f"\n\n💡 尝试浏览上级目录：`/dlna-cast` `webdav` `browse` `'{parent_path}'`"
                    yield event.plain_result(result)
                else:
                    yield event.plain_result(f"❌ {message}")
                return

            # 保存新的当前路径到会话
            event._current_webdav_path = new_path
            logger.info(f"更新当前路径为: {new_path}")

            if not items:
                result = f"📁 路径 '{new_path}' 下没有找到可浏览的内容"
                # 尝试列出上级目录作为提示
                parent_path = os.path.dirname(new_path.rstrip('/'))
                if parent_path and parent_path != new_path:
                    result += f"\n\n💡 尝试浏览上级目录：`/dlna-cast` `webdav` `browse` `'{parent_path}'`"
            else:
                result = f"📁 WebDAV【{selected_config['name']}】- 当前路径: {new_path}\n"
                result += "=" * 40 + "\n\n"

                # 分类显示目录和文件
                dirs = [item for item in items if item.is_dir]
                files = [item for item in items if not item.is_dir]

                if dirs:
                    result += "📂 目录：\n"
                    for i, d in enumerate(dirs, 1):
                        result += f"  {i}. 📁 {d.name}\n"
                        # 生成进入子目录的命令
                        result += f"     进入: `/dlna-cast` `webdav` `browse` `{new_path.rstrip('/')}/{d.name}`\n"
                    result += "\n"

                if files:
                    result += "🎬 视频文件：\n"
                    for i, f in enumerate(files, 1):
                        # 格式化文件大小
                        size = f.size
                        if size < 1024:
                            size_str = f"{size}B"
                        elif size < 1024 * 1024:
                            size_str = f"{size / 1024:.1f}KB"
                        elif size < 1024 * 1024 * 1024:
                            size_str = f"{size / 1024 / 1024:.1f}MB"
                        else:
                            size_str = f"{size / 1024 / 1024 / 1024:.2f}GB"

                        # 生成播放命令
                        if ' ' in f.name:
                            result += f"  {i}. 🎥 {f.name} ({size_str}) (⚠️ 包含空格)\n"
                            result += f"     播放: /dlna-cast play '{new_path.rstrip('/')}/{f.name}'\n"
                        else:
                            result += f"  {i}. 🎥 {f.name} ({size_str})\n"
                            result += f"     播放: /dlna-cast play {new_path.rstrip('/')}/{f.name}\n"

                result += f"\n💡 统计: {len(dirs)} 个目录，{len(files)} 个视频文件"

                # 添加导航提示
                result += "\n\n📝 导航提示："
                if new_path != '/':
                    result += f"\n• 返回上级: `/dlna-cast` `webdav` `browse` `..`"
                result += "\n• 返回根目录: `/dlna-cast` `webdav` `browse` `/`"
                result += "\n• 查看所有服务器: `/dlna-cast` `webdav` `ls`"

                # 添加播放提示
                if files:
                    result += "\n\n🎯 播放提示："
                    result += "\n• 播放视频: `/dlna-cast` `play` `完整路径`"
                    result += "\n• 暂停: `/dlna-cast` `pause`"
                    result += "\n• 继续: `/dlna-cast` `replay`"

        except Exception as e:
            logger.error(f"webdav_browse 异常: {e}")
            result = f"❌ 浏览失败: {str(e)}"

        self.db.log_message(event, inspect.currentframe().f_code.co_name, params_dict, result)
        yield event.plain_result(result)

    @dlna_cast.group("dlna")
    def dlna(self, event: AstrMessageEvent):
        pass

    @dlna.command("help")
    async def dlna_help(self, event: AstrMessageEvent):
        """dlna 指令帮助"""
        # TODO
        yield event.plain_result(f"dlna 指令帮助")

    @dlna.command("scan")
    async def dlan_scan(self, event: AstrMessageEvent):
        """dlna 设备扫描"""
        # TODO
        yield event.plain_result(f"dlna 扫描")

    @dlna.command("ls")
    async def dlan_ls(self, event: AstrMessageEvent):
        """dlna 设备列表查看"""
        # TODO
        yield event.plain_result(f"dlna 列表查看")

    @dlna.command("add")
    async def dlan_add(self, event: AstrMessageEvent, index: int, name: str = None):
        """dlna 设备添加"""
        # TODO
        yield event.plain_result(f"dlna 设备添加")

    @dlna.command("select")
    async def dlan_select(self, event: AstrMessageEvent, index: int):
        """dlna 设备选中"""
        # TODO
        yield event.plain_result(f"dlna 设备选中, index: {index}")

    @dlna.command("rm")
    async def dlan_remove(self, event: AstrMessageEvent, index: int):
        """dlna 设备删除"""
        # TODO
        yield event.plain_result(f"dlna 设备删除, index: {index}")

    @dlna_cast.command("play")
    async def dlna_cast_play(self, event: AstrMessageEvent, text: str):
        """视频播放"""
        logger.debug("触发 /dlna-cast play 指令")
        # TODO: 调用DLNA播放接口
        yield event.plain_result("play 指令已成功下达")

    @dlna_cast.command("replay")
    async def dlna_cast_replay(self, event: AstrMessageEvent):
        """视频重播"""
        logger.debug("触发 /dlna-cast replay 指令")
        # TODO: 调用DLNA播放接口
        yield event.plain_result("replay 指令已成功下达")

    @dlna_cast.command("pause")
    async def dlna_cast_pause(self, event: AstrMessageEvent):
        """视频暂停"""
        logger.debug("触发 /dlna-cast pause 指令")
        # TODO: 调用DLNA暂停接口
        yield event.plain_result("pause 指令已成功下达")

    @dlna_cast.command("stop")
    async def dlna_cast_stop(self, event: AstrMessageEvent):
        """视频停止"""
        logger.debug("触发 /dlna-cast stop 指令")
        # TODO: 调用DLNA停止接口
        yield event.plain_result("stop 指令已成功下达")

    @dlna_cast.command("seek")
    async def dlna_cast_seek(self, event: AstrMessageEvent, position: str):
        """视频播放跳转"""
        logger.debug(f"触发 /dlna-cast seek 指令，目标位置: {position}")
        # TODO: 调用DLNA跳转接口
        yield event.plain_result(f"seek 指令已成功下达，目标位置: {position}")

    @dlna_cast.command("status")
    async def dlna_cast_status(self, event: AstrMessageEvent):
        """播放状态查询"""
        logger.debug(f"触发 /dlna-cast status 指令")
        # TODO: 调用DLNA跳转接口
        yield event.plain_result(f"status 指令已成功下达")

    @dlna_cast.command("history")
    async def dlna_cast_history(self, event: AstrMessageEvent):
        """播放历史查询"""
        logger.debug(f"触发 /dlna-cast history 指令")
        # TODO: 返回播放历史信息
        yield event.plain_result(f"history 指令已成功下达")

    @dlna_cast.command("say")
    async def dlna_cast_say(self, event: AstrMessageEvent, text: str):
        """自然语言文字操控，详见 /dlna-cast help """
        logger.debug(f"触发 /dlna-cast say 指令，text: {text}")
        # TODO: 调用DLNA控制接口
        yield event.plain_result(f"say 指令已成功下达，text: {text}")

    async def terminate(self):
        """可选择实现 terminate 函数，当插件被卸载/停用时会调用。"""
        self.db.close()
        logger.info("数据库连接已关闭")