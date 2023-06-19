import os
import time
from urllib.parse import urlencode

import requests

from DataAcquirer import retry
from DataAcquirer import sleep
from Parameter import XBogus
from Recorder import RunLogger
from StringCleaner import Cleaner


def reset(function):
    """重置数据"""

    def inner(self, *args, **kwargs):
        self.type_ = {"video": "", "images": ""}  # 文件保存目录
        self.video_data = []
        self.image_data = []
        self.video = 0  # 视频下载数量
        self.image = 0  # 图集下载数量
        self.image_id = None  # 临时记录图集ID，用于下载计数
        return function(self, *args, **kwargs)

    return inner


class Download:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        'referer': 'https://www.douyin.com/',
    }  # 请求头
    video_id_api = "https://aweme.snssdk.com/aweme/v1/play/"  # 官方视频下载接口
    item_ids_api = "https://www.douyin.com/aweme/v1/web/aweme/detail/"  # 官方信息接口
    clean = Cleaner()  # 过滤非法字符
    length = 128  # 文件名称长度限制
    chunk = 1048576  # 单次下载文件大小，单位字节

    def __init__(self, log: RunLogger, save):
        self.xb = XBogus()
        self.log = log  # 日志记录模块
        self.data = save  # 详细数据记录模块
        self._cookie = False
        self._nickname = None  # 账号昵称
        self._root = None
        self._name = None
        self._time = None
        self._split = None
        self._folder = None
        self._music = False  # 是否下载音乐
        self._dynamic = False  # 是否下载动态封面图
        self._original = False  # 是否下载静态封面图
        self.type_ = {"video": "", "images": ""}  # 文件保存目录
        self.video_data = []  # 视频详细信息
        self.image_data = []  # 图集详细信息
        self.video = 0  # 视频下载数量
        self.image = 0  # 图集下载数量
        self.image_id = None  # 临时记录图集ID，用于下载计数
        self.proxies = None  # 代理

    @property
    def time(self):
        return self._time

    @time.setter
    def time(self, value):
        if value:
            try:
                _ = time.strftime(value, time.localtime())
                self._time = value
                self.log.info(f"时间格式设置成功: {value}", False)
            except ValueError:
                self.log.warning(f"时间格式错误: {value}，将使用默认时间格式（年-月-日 时.分.秒）")
                self._time = "%Y-%m-%d %H.%M.%S"
        else:
            self.log.warning("非法的时间格式，将使用默认时间格式（年-月-日 时.分.秒）")
            self._time = "%Y-%m-%d %H.%M.%S"

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if value:
            dict_ = {
                "id": 0,
                "desc": 1,
                "create_time": 2,
                "author": 3,
            }
            name = value.strip().split(" ")
            try:
                self._name = [dict_[i] for i in name]
                self.log.info(f"命名格式设置成功: {value}", False)
            except KeyError:
                self.log.warning(f"命名格式错误: {value}，将使用默认命名格式（创建时间 作者 描述）")
                self._name = [2, 3, 1]
        else:
            self.log.warning("非法的命名格式，将使用默认命名格式（创建时间 作者 描述）")
            self._name = [2, 3, 1]

    def get_name(self, data: list) -> str:
        """生成文件名称"""
        return self.clean.filter(self.split.join(data[i] for i in self.name))

    @property
    def split(self):
        return self._split

    @split.setter
    def split(self, value):
        if value:
            for s in value:
                if s in self.clean.rule.keys():
                    self.log.warning(f"无效的文件命名分隔符: {value}，默认使用“-”作为分隔符！")
                    self._split = "-"
                    return
            self._split = value
            self.log.info(f"命名分隔符设置成功: {value}", False)
        else:
            self.log.warning("非法的文件命名分隔符，默认使用“-”作为分隔符！")
            self._split = "-"

    @property
    def folder(self):
        return self._folder

    @folder.setter
    def folder(self, value):
        if value:
            for s in value:
                if s in self.clean.rule.keys():
                    self.log.warning(
                        f"无效的下载文件夹名称: {value}，默认使用“Download”作为下载文件夹名称！")
                    self._folder = "Download"
                    return
            self._folder = value
            self.log.info(f"下载文件夹名称设置成功: {value}", False)
        else:
            self.log.warning("非法的下载文件夹名称！默认使用“Download”作为下载文件夹名称！")
            self._folder = "Download"

    @property
    def root(self):
        return self._root

    @root.setter
    def root(self, value):
        if os.path.exists(value) and os.path.isdir(value):
            self._root = value
            self.log.info(f"文件保存路径设置成功: {value}", False)
        else:
            self.log.warning(f"文件保存路径错误: {value}，将使用当前路径作为保存路径！")
            self._root = "./"

    @property
    def music(self):
        return self._music

    @music.setter
    def music(self, value):
        if isinstance(value, bool):
            self._music = value
            self.log.info(f"是否下载视频/图集的音乐: {value}", False)
        else:
            self.log.warning(f"音乐下载设置错误: {value}，默认不下载视频/图集的音乐！")
            self._music = False

    @property
    def dynamic(self):
        return self._dynamic

    @dynamic.setter
    def dynamic(self, value):
        if isinstance(value, bool):
            self._dynamic = value
            self.log.info(f"是否下载视频动态封面图: {value}", False)
        else:
            self.log.warning(f"动态封面图下载设置错误: {value}，默认不下载视频动态封面图！")
            self._dynamic = False

    @property
    def original(self):
        return self._original

    @original.setter
    def original(self, value):
        if isinstance(value, bool):
            self._original = value
            self.log.info(f"是否下载视频封面图: {value}", False)
        else:
            self.log.warning(f"封面图下载设置错误: {value}，默认不下载视频封面图！")
            self._original = False

    @property
    def nickname(self):
        return self._nickname

    @nickname.setter
    def nickname(self, value):
        if name := self.clean.filter(value):
            self._nickname = name
            self.log.info(f"账号昵称: {value}, 去除非法字符后: {name}", False)
        else:
            self._nickname = str(time.time())[:10]
            self.log.error(f"无效的账号昵称，原始昵称: {value}, 去除非法字符后: {name}")
            self.log.warning(f"本次运行将默认使用当前时间戳作为帐号昵称: {self._nickname}")

    @property
    def cookie(self):
        return self._cookie

    @cookie.setter
    def cookie(self, cookie):
        if isinstance(cookie, str):
            self.headers["Cookie"] = cookie
            self._cookie = True

    def create_folder(self, folder):
        """创建作品保存文件夹"""
        root = os.path.join(self.root, folder)
        if not os.path.exists(root):
            os.mkdir(root)
        self.type_["video"] = os.path.join(root, "video")
        if not os.path.exists(self.type_["video"]):
            os.mkdir(self.type_["video"])
        self.type_["images"] = os.path.join(root, "images")
        if not os.path.exists(self.type_["images"]):
            os.mkdir(self.type_["images"])

    @retry(max_num=5)
    def get_data(self, item):
        """获取作品详细信息"""
        params = {
            "aweme_id": item,
            "aid": "6383",
            "cookie_enabled": "true",
            "platform": "PC",
            "downlink": "10"
        }
        xb = self.xb.get_x_bogus(urlencode(params))
        params["X-Bogus"] = xb
        for _ in range(3):  # 获取数据为空时重新尝试
            try:
                response = requests.get(
                    self.item_ids_api,
                    params=params,
                    proxies=self.proxies,
                    headers=self.headers, timeout=10)
                sleep()
                if response.status_code == 200 and response.text:
                    try:
                        return response.json()["aweme_detail"]
                    except (KeyError, IndexError):
                        self.log.error(f"响应内容异常: {response.json()}", False)
                        return False
            except requests.exceptions.ReadTimeout:
                continue
        self.log.error(
            f"资源 {item} 获取 item_list 失败！")
        return False

    def get_info(self, data, type_):
        """
        提取作品详细信息
        视频格式: 作品ID, 描述, 创建时间, 作者, 视频ID, [音乐名称, 音乐链接], 动态封面图, 静态封面图
        图集格式: 作品ID, 描述, 创建时间, 作者, 图集链接, [音乐名称, 音乐链接]
        """
        for item in data:
            item = self.get_data(item)
            id_ = item["aweme_id"]
            desc = self.clean.filter(item["desc"] or id_)
            create_time = time.strftime(
                self.time,
                time.localtime(
                    item["create_time"]))
            music_name = f'{item["music"]["author"]}-{item["music"]["title"]}'
            music = u[0] if (u := item["music"]["play_url"]
            ["url_list"]) else None  # 部分作品的数据没有音乐下载地址
            if type_ == "Video":
                video_id = item["video"]["play_addr"]["uri"]
                # 动态封面图链接
                dynamic_cover = item["video"]["dynamic_cover"]["url_list"][0]
                # 封面图链接
                cover_original_scale = item["video"]["cover_original_scale"]["url_list"][0]
                self.log.info(
                    "视频: " +
                    ",".join(
                        [
                            id_,
                            desc,
                            create_time.replace(
                                ".",
                                ":"),
                            self.nickname,
                            video_id]),
                    False)
                self.data.save(["视频", id_, desc, create_time.replace(
                    ".", ":"), self.nickname, video_id])
                self.video_data.append([id_, desc, create_time, self.nickname, video_id, [
                    music_name, music], dynamic_cover, cover_original_scale])
            elif type_ == "Image":
                images = item["images"]
                images = [i['url_list'][3] for i in images]
                self.log.info(
                    "图集: " + ",".join([id_, desc, create_time.replace(".", ":"), self.nickname]), False)
                self.data.save(
                    ["图集", id_, desc, create_time.replace(".", ":"), self.nickname, "#"])
                self.image_data.append(
                    [id_, desc, create_time, self.nickname, images, [music_name, music]])
            else:
                raise ValueError("type_ 参数错误！应该为 Video 或 Image 其中之一！")

    def download_images(self):
        root = self.type_["images"]
        for item in self.image_data:
            for index, image in enumerate(item[4]):
                with requests.get(
                        image,
                        stream=True,
                        proxies=self.proxies,
                        headers=self.headers) as response:
                    name = self.get_name(item)
                    self.save_file(
                        response,
                        root,
                        f"{name}_{index + 1}",
                        "jpeg",
                        item[0])
                self.image_id = item[0]
            sleep()
            self.download_music(root, item)

    def download_video(self):
        root = self.type_["video"]
        for item in self.video_data:
            params = {
                "video_id": item[4],
                "ratio": "1080p",
            }
            with requests.get(
                    self.video_id_api,
                    params=params,
                    stream=True,
                    proxies=self.proxies,
                    headers=self.headers) as response:
                name = self.get_name(item)
                self.save_file(response, root, name, "mp4")
            sleep()
            self.download_music(root, item)
            self.download_cover(root, name, item)

    def download_music(self, root: str, item: list):
        """下载音乐"""
        if self.music and (u := item[5][1]):
            with requests.get(
                    u,
                    stream=True,
                    proxies=self.proxies,
                    headers=self.headers) as response:
                self.save_file(
                    response,
                    root,
                    self.clean.filter(f"{f'{item[0]}-{item[5][0]}'}"),
                    "mp3",
                )
            sleep()

    def download_cover(self, root: str, name: str, item: list):
        """下载静态/动态封面图"""
        if not self.dynamic and not self.original:
            return
        if self.dynamic and (u := item[6]):
            with requests.get(
                    u,
                    stream=True,
                    proxies=self.proxies,
                    headers=self.headers) as response:
                self.save_file(
                    response,
                    root,
                    name,
                    "webp")
        if self.original and (u := item[7]):
            with requests.get(
                    u,
                    stream=True,
                    proxies=self.proxies,
                    headers=self.headers) as response:
                self.save_file(
                    response,
                    root,
                    name,
                    "jpeg")
        sleep()

    def save_file(self, data, root: str, name: str, type_: str, id_=""):
        """保存文件"""
        file = os.path.join(root, f"{name[:self.length].strip()}.{type_}")
        if os.path.exists(file):
            self.log.info(f"{name[:self.length].strip()}.{type_} 已存在，跳过下载！")
            self.log.info(
                f"文件保存路径: {file}", False)
            return True
        with open(file, "wb") as f:
            for chunk in data.iter_content(chunk_size=self.chunk):
                f.write(chunk)
        """图集下载数量汇总存在Bug，暂时停用"""
        # if type_ == "mp4":
        #     self.video += 1
        # elif type_ == "webp" and id_ != self.image_id:
        #     self.image += 1
        self.log.info(f"{name[:self.length].strip()}.{type_} 下载成功！")
        self.log.info(
            f"文件保存路径: {file}",
            False)

    def summary(self):
        """汇总下载数量"""
        return
        # self.log.info(f"本次运行下载视频数量: {self.video}")
        # self.log.info(f"本次运行下载图集数量: {self.image}")
        # self.video = 0
        # self.image = 0

    @reset
    def run(self, video: list[str], image: list[str]):
        """批量下载"""
        self.create_folder(self.nickname)
        self.log.info("开始获取作品数据！")
        self.get_info(video, "Video")
        self.get_info(image, "Image")
        self.log.info("获取作品数据成功！")
        self.log.info("开始下载视频/图集！")
        self.download_video()
        self.download_images()
        self.log.info("视频/图集下载结束！")
        self.summary()

    @reset
    def run_alone(self, id_: str):
        """单独下载"""
        if not self.folder:
            self.log.warning("未设置下载文件夹名称！")
            return False
        self.create_folder(self.folder)
        data = self.get_data(id_)
        if not data:
            print("下载作品失败！")
            return False
        self.nickname = self.clean.filter(data["author"]["nickname"])
        if data["images"]:
            self.get_info([id_], "Image")
            self.download_images()
        else:
            self.get_info([id_], "Video")
            self.download_video()
        return True
