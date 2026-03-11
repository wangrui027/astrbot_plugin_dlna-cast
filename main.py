import inspect
import os

from astrbot.api import logger  # 使用 astrbot 提供的 logger 接口
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

from .ctr.db_utils import DatabaseManager

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
        # TODO
        yield event.plain_result(f"webdav 指令帮助")

    @webdav.command("add")
    async def webdav_add(self, event: AstrMessageEvent, name: str, url: str, username: str = None,
                         password: str = None):
        """webdav 服务器添加"""
        logger.info("触发 /dlna-cast webdav add 指令")
        params_dict = {
            'name': name,
            'url': url,
            'username': username,
            'password': password
        }
        # TODO
        result = f"webdav服务【{name}】已添加"
        self.db.log_message(event, inspect.currentframe().f_code.co_name, params_dict, result)
        yield event.plain_result(result)

    @webdav.command("ls")
    async def webdav_ls(self, event: AstrMessageEvent):
        """webdav 服务器列表查看"""
        # TODO
        yield event.plain_result(f"webdav 服务器列表查看")

    @webdav.command("select")
    async def webdav_select(self, event: AstrMessageEvent, index: int):
        """webdav 服务器选中"""
        # TODO
        yield event.plain_result(f"webdav 服务器选中, index: {index}")

    @webdav.command("rm")
    async def webdav_rm(self, event: AstrMessageEvent, index: int):
        """webdav 服务器删除"""
        # TODO
        yield event.plain_result(f"webdav 服务器删除, index: {index}")

    @webdav.command("browse")
    async def webdav_browse(self, event: AstrMessageEvent, path: str = "/"):
        """webdav 资源浏览"""
        # TODO
        yield event.plain_result(f"webdav 资源浏览, path: {path}")

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
