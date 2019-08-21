# coding=UTF-8

import random
import time
import requests
from bs4 import BeautifulSoup
import base64
import re
import csv
from io import BytesIO
from fontTools.ttLib import TTFont
from pymongo import MongoClient

# mongodb对象
conn = MongoClient('127.0.0.1', 27017)
db = conn.anjuke  # 选择或者创建数据库
my_set = db.house_info  # 集合

# 数字和租房押金关系， 没有对应填0
reting_dict = {
    '1': '付1押2', "2": '付2押1',
    '3': '付2押2', '4': '付3押1',
    '5': '付3押2', '6': '面议',
    '7': '半年付', '8': '年付',
    '9': '半年付押1', '10': '年付押1',
    '11': '付1押1'
}

# refer是访问的来源网页
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
}
# 写入csv文件的
csv_file = open('anjuke.csv', 'w', newline='')
writer = csv.writer(csv_file)

def main():
    base_url = 'https://hz.zu.anjuke.com/fangyuan/p'
    url_list = get_page_url(base_url, 51)
    # 遍历50页的内容
    for i in range(0, len(url_list)):
        s = requests.session()
        s.keep_alive = False  # 关闭多余连接
        response = requests.get(url=url_list[i], headers=headers)
        html_str = response.text

        # print(html_str)
        parse_page(html_str)
        time_sl = random.randint(3,10)
        time.sleep(time_sl)
        # html_thread = Thread(target=parse_page, args=[html_str, ])
        # html_thread.start()
    # print(response.text)


def parse_page(html_str):
    # 破解数字用的编码，网页上获取的
    try:
        bs64_str = re.findall("charset=utf-8;base64,(.*?)'\)", html_str)[0]
    except:
        time.sleep(random.choice(5))
        print('出错，休息0-5秒')
    # soup对象
    soup = BeautifulSoup(html_str, 'lxml')
    div_list = soup.select('.zu-itemmod')
    # print(len(div_list))
    # 这个是进入一定的次数就休息
    time_visit = random.randint(20, 40)
    num_visit = 0  # 达到次数
    # 从中获取数据
    for tag in div_list:
        my_list = ['杭州']
        # print(tag)
        # print('#################')
        '''
        *小区户型/分类	*户型类型	*小区户型/标准面积	*小区户型/面积区间	小区户型租金/毛坯	*小区户型租金/简易装修	*小区户型租金/精装修	小区户型租金/豪华装修	*小区户型租金/付款方式	*更新时间
        一房一厅	1.标准平面	88.44	85-95	12500	14000	15500	17000	4	2018/5/14'''
        # 小区名
        plot_name = tag.select('address a')[0].get_text()
        # 小区地址
        plot_address = tag.select('address')[0].get_text()
        # 对小区地址进行操作去除小区名
        plot_address = plot_address.replace(plot_name, '', 1)
        plot_address = plot_address.strip()
        add_list = plot_address.split(' ')  # 列表第一个数据是小区的行政区，第二个是具体地址
        my_list.extend(add_list)  # 添加数据
        my_list.append(plot_name)  # 小区名
        # 小区户型、分类 三个数据分别是几室几厅，多少平米
        house_type_list = tag.select("b[style='font-weight: normal;']")
        house_list = []
        for each in house_type_list:
            # 列表，三个数据分别是几室几厅，多少平米,几厅可能为空
            data_str = get_page_show_ret(each.get_text(), bs64_str)
            house_list.append(data_str)
        my_list.append(house_list[0] + '室' + house_list[1] + '厅')
        my_list.append('1.标准平面')
        my_list.append(house_list[2])  # 这是多少平米
        # 小区租金，这个是价格转码
        price_str = tag.select('strong b')[0].get_text()
        ret = get_page_show_ret(price_str, bs64_str)
        my_list.append(ret)
        # 根据访问二级页面次数来定时休息
        num_visit += 1
        if num_visit == time_visit:
            time_sl = random.randint(3, 10)
            time.sleep(time_sl)
            num_visit = 0
        # 根据链接来获得下面两个值 付款方式 更新时间
        a_list = tag.select("a[class='img']")[0]
        ret_list = get_content(a_list.attrs['href'])  # 返回付款方式和时间
        my_list.extend(ret_list)
        # print(my_list)
        # 写入csv一行
        # writer.writerow(my_list)
        # 写入mongodb
        title_list = ['城市', '行政区', '小区地址', '小区名称', '小区户型', '户型类型', '面积', '租金', '租金付款方式', '更新时间']
        mongo_dict = dict(zip(title_list, my_list))
        my_set.insert_one(mongo_dict)


def get_page_url(base_url, num):
    # 获取网页地址列表
    ret_list = []
    for i in range(1, num):
        ret_list.append(base_url+str(i))
    return ret_list


def get_page_show_ret(mystr, bs64_str):
    '''
    :param mystr: 要转码的字符串
    :param bs64_str:  转码格式
    :return: 转码后的字符串
    '''
    font = TTFont(BytesIO(base64.decodebytes(bs64_str.encode())))
    c = font['cmap'].tables[0].ttFont.tables['cmap'].tables[0].cmap
    ret_list = []
    for char in mystr:
        decode_num = ord(char)
        if decode_num in c:
            num = c[decode_num]
            num = int(num[-2:]) - 1
            ret_list.append(num)
        else:
            ret_list.append(char)
    ret_str_show = ''
    for num in ret_list:
        ret_str_show += str(num)
    return ret_str_show


def get_content(href):
    # 根据链接获取内容  付款方式和时间
    # 这个时间也是加密的
    ret_list = []
    # 获取网页内容和解码格式
    html_str = requests.get(href, headers=headers).text
    # print(html_str)
    bs64_str = re.findall("charset=utf-8;base64,(.*?)'\)", html_str)[0]

    soup = BeautifulSoup(html_str, 'lxml')
    div_list = soup.select("div[class='lbox']")
    for tag in div_list:
        time_str = tag.select("div[class='right-info']")[0].get_text()
        time_str = time_str[-11:]  # 切割时间
        time_str = get_page_show_ret(time_str, bs64_str)
        pay_method = tag.select("span[class='type']")[0].get_text()
        # 根据这个值获取键名
        pay_str = list(reting_dict.keys())[list(reting_dict.values()).index(pay_method)]
        ret_list.append(pay_str)
        ret_list.append(time_str)
        # print('$$$$$$$$$$$$$$$$$$$')
    return ret_list


def write_csv_title():
    # 写入标题，只用一次
    '''城市	行政区	小区名称	*小区户型/分类	*户型类型	*小区户型/标准面积	*小区户型/面积区间	小区户型租金/毛坯	*小区户型租金/简易装修	*小区户型租金/精装修	小区户型租金/豪华装修	*小区户型租金/付款方式	*更新时间'''
    title_list = ['城市', '行政区', '小区地址', '小区名称', '小区户型', '户型类型', '面积', '租金', '租金付款方式', '更新时间']
    writer.writerow(title_list)


#  龒閏驋驋   龤閏驋驋
if __name__ == '__main__':
    # write_csv_title()
    main()
