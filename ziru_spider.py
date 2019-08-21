import requests
import random
import time
from bs4 import BeautifulSoup
import re
import csv
import io
from PIL import Image
import pytesseract
from pymongo import MongoClient
# 这是自如爬虫


class ZiruPa(object):

    def __init__(self):
        # 'Referer: http://hz.ziroom.com/z/z0-p2/'
        self.headers = {'Referer' : 'http://hz.ziroom.com/z/z0-p1/','User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36"}
        self.base_url = 'http://hz.ziroom.com/z/z0-p'
        # 这个是px对应的数字
        self.img_px_list = ['0', '21.4', '42.8', '64.2', '85.6', '107', '128.4', '149.8', '171.2', '192.6']
        # 要保存的数据列表
        self.house_info_list = []
        # 写入csv文件的
        self.csv_file = open('ziru.csv', 'w', newline='')
        self.writer = csv.writer(self.csv_file)

    def mongo_download_continue(self):
        # mongodb对象
        conn = MongoClient('127.0.0.1', 27017)
        db = conn.ziru  # 选择或者创建数据库
        my_set = db.url_num  # 集合 # 要写入的是具体哪一页的第几个数据


    def start(self):
        s = requests.session()
        s.keep_alive = False  # 关闭多余连接
        # 先写入第一行csv       # 写入mongodb之后在写
        title_list = ['城市', '行政区', '小区地址', '小区名称', '小区户型', '户型类型', '面积', '租金', '租金付款方式', '更新时间']
        self.writer.writerow(title_list)
        url_list = self.set_page_num(50)
        for url in url_list:
            # 获取当前网页
            html_str = requests.get(url, headers=self.headers).text
            # 获取soup对象
            soup = BeautifulSoup(html_str, 'lxml')
            item_div_list = soup.select("div[class='item']")
            # 设置当前页面的来源网页
            self.headers['Referer'] = url
            # 遍历每个详情页
            for div_item in item_div_list:
                # 直接获取价格
                price_str = self.get_price(div_item)
                # 有一个是广告页，所以判断下
                if price_str != '':
                    # 获取详情链接
                    detail_url = 'http:' + div_item.select("a[class='pic-wrap']")[0].attrs['href']
                    # print(detail_url)
                    # 进入详情页获取要爬的数据，返回的是列表
                    self.house_info_list = self.get_detail_list(detail_url)
                    self.house_info_list.insert(7, price_str)
                    self.writer.writerow(self.house_info_list)
                    print('爬完一个详情页')
                    # print(self.house_info_list)

                #     杭州	余杭-未来科技城	文昌路,近常二路	福鼎家园	3室1厅	1.标准平面	20	800	付1押1	2019年07月08日

            # 随机休息1-5的小数秒
            print('爬完一个列表')
            time.sleep(random.uniform(1, 5))

    def set_page_num(self, num):
        '''
        还要设置refer地址
        :param num: 设置要爬的页数，1页30个数据-1
        :return: 返回列表都是地址
        '''
        ret_list = []
        for i in range(1,num+1):
            url = self.base_url + str(i) + '/'
            ret_list.append(url)
        return ret_list

    def get_detail_list(self, detail_url):
        # 要返回的列表
        ret_list = ['杭州']
        detail_html_str = requests.get(detail_url, headers=self.headers).text
        # 处理详情页的soup对象
        soup = BeautifulSoup(detail_html_str, 'lxml')
        # todo 1.获取行政地址 比如西湖三墩
        z_container = soup.select("div[class='Z_container Z_bread mt60']")[0]
        re_ret = re.findall('[/](.*?)[/]',z_container.get_text())  # 正则匹配内容
        ret_list.append(re_ret[0].replace(' ', ''))   # 添加行政地址
        # todo 2.获取小区地址
        address_list = soup.select("ul[class='Z_home_o'] li")
        ret_list.append(address_list[0].get_text().replace('位置', '').strip())  # 地址
        # todo 3.小区名称
        re_ret1 = re.findall('[/].*?[/](.*?)[租]', z_container.get_text())
        xiaoqu_str = re_ret1[0].replace(' ', '')  # 有合租和整租，去除最后一位
        ret_list.append(xiaoqu_str[0:-1])  # 添加小区名称
        # todo 4.小区户型
        z_bome_list = soup.select("div[class='Z_home_b clearfix'] dd")
        ret_list.append(z_bome_list[2].get_text().strip())  # 去除户型和空格换行符
        # todo 5.户型类型，写楼层好了
        ret_list.append(address_list[1].get_text().strip())
        # todo 6.面积
        ret_list.append(z_bome_list[0].get_text().strip())
        # todo 7.租金付款方式
        z_price = soup.select("div[class='Z_price'] span")[1]
        re_ret2 = re.findall('[（](.*?)[）]', z_price.get_text())  # 截取（）内容，中文符号的括号
        ret_list.append(re_ret2[0])
        # todo 8.更新时间
        ret_list.append(address_list[3].get_text().replace('年代', '').strip())
        # 返回列表
        return ret_list

    def get_price(self, div_item):
        # 拼接的字符串
        price_str = ''
        num_list = div_item.select("div[class='price'] span[class='num']")
        # 总共四个数字或更多，需要遍历
        for num in num_list:
            style= num.attrs['style']  # style包含的数据
            list1 = re.findall(r'[(](.*?)[)]', style)
            list2 = re.findall(r'[-](.*?)[px]', style)
            img_url = 'http:'+list1[0]
            ret = self.parse_img(img_url)
            # 获取对应下标
            index = self.img_px_list.index(list2[3])
            # 拼接字符串 一个num_list循环就是一个价格
            price_str = price_str + ret[index]

        return price_str


    def parse_img(self, img_url):
        '''
        :param img_url: 图片链接 "http://static8.ziroom.com/phoenix/pc/images/price/new-list/f4c1f82540f8d287aa53492a44f5819b.png"
        :return: 返回列表
        '''
        data = requests.get(url=img_url, headers=self.headers).content
        image = Image.open(io.BytesIO(data))
        vcode = pytesseract.image_to_string(image, lang='eng',
                                            config='--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789').strip()
        ret_list = []
        for i in vcode:
            ret_list.append(i)
        # 可能或出现斜杠/或者读取不出
        try:
            ret_list.remove('/')
        except:
            pass
        return ret_list


if __name__ == '__main__':
    ziru = ZiruPa()
    ziru.start()
    # ziru.parse_img('http://static8.ziroom.com/phoenix/pc/images/price/da4554c01a8c0563bf7fc106c3934722s.png')
