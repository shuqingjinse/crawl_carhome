"""
@file:run_the_spider.py
@time:2020/1/18-22:27
"""
import json
import re

import execjs
import requests

import pandas as pd


class AutoHome:
    def __init__(self):
        # self.url = "https://car.autohome.com.cn/config/spec/42595.html#pvareaid=3454541"
        self.url = "https://car.autohome.com.cn/config/series/4851.html#pvareaid=3454437"
        self.headers = {
            "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.90 Safari/537.36",
        }
        self.config_pattern = r'var config = (.*?);'
        self.option_pattern = r'var option = (.*?});'

        self.car_content_dict = {}

        self.origin_text = r"$InsertRule$($index$, $temp$);"
        self.dest_text = r"words[$GetClassName$($index$)] = $temp$;"

        self.content_func = """
function get_words(){
    func(document);
    return words;
}
"""

        self.content_prefix = """
const jsdom = require("jsdom");
const {JSDOM} = jsdom;
const dom = new JSDOM();
window = dom.window;
document = window.document;
window.decodeURIComponent = decodeURIComponent;
var words = {};

"""

    def get_html(self):
        """
        获取页面源码
        :return:
        """
        resp = requests.get(url=self.url, headers=self.headers, timeout=3)
        # resp.raise_for_status()
        html = resp.text
        return html

    def modify_run_js(self, jsfile, car_config_def, dtype=1):
        """
        拼接成可供execjs进行调用的形式
        :param jsfile:
        :return:
        """
        configJs = self.content_prefix + "var func =" + jsfile.replace(self.origin_text,
                                                                       self.dest_text) + self.content_func
        car_info_dict = self.js_exec(configJs, car_config_def)
        car_name_dict = []
        if dtype == 1:
            # 获取车型名称的字典 {'specid': 39464, 'value': '宝马X3 2019款 xDrive25i 豪华套装'},
            paramitems_list = car_info_dict['result']['paramtypeitems'][0]['paramitems'][0]['valueitems']

            # 构造ID 对应 车名 的字典
            car_name_dict = dict([(param['specid'], param['value']) for param in paramitems_list])

            for i,v in car_name_dict.items():
                self.car_content_dict[v] = {}

        return car_info_dict,car_name_dict

    def js_exec(self, js_file, car_info_str):
        """

        :param js_file:
        :param car_info_str:
        :return:
        """
        ctx = execjs.compile(js_file, cwd=r'D:\code\node-v12.9.0-win-x64\node_modules')
        words = ctx.call('get_words')
        # {'.hs_kw0_configmy': '适', '.hs_kw1_configmy': '万'
        for k, v in words.items():
            k = k.replace('.', '').strip()
            car_info_str = car_info_str.replace("<span class='" + k + "'></span>", v)

        car_info_dict = json.loads(car_info_str)
        return car_info_dict

    def get_option_item(self, info_dict, car_name_dict=None, op_id=None):
        """
        通过车型id获取某一项
        :param info_dict:
        :param op_id: 某配置项ID
        :param car_name_dict: 车型ID对应车名
        :return:
        """
        if isinstance(info_dict, str):
            info_dict = json.loads(info_dict)

        info_list = info_dict['result']['configtypeitems']
        # data = dict()
        # for info in info_list:
        #     for item in info['configitems']:
        #         data[item['id']] = item['name']
        # for specid, car_name in car_name_dict.items():
        #     # {'price': [], 'specid': 39464, 'sublist': [], 'value': '主●&nbsp;/&nbsp;副●'}
        #     for value_dict in item['valueitems']:
        #         data[specid] = value_dict["value"]
        data = {item['id']: item['name'] for info in info_list for item in info['configitems']}
        print(data)

    def get_car_content(self, info_dict, car_name_dict, car_content_dict, type):
        """
        通过车型id获取某一项
        :param info_dict:
        :param op_id: 某配置项ID
        :param car_name_dict: 车型ID对应车名
        :return:
        """
        if isinstance(info_dict, str):
            info_dict = json.loads(info_dict)

        if type == 'config':
            info_list = info_dict['result']['paramtypeitems'] 
            key_info = 'paramitems'
        elif type == 'option':
            info_list = info_dict['result']['configtypeitems']
            key_info = 'configitems'

        index_name = []
        for info in info_list:
            for item in info[key_info]:
                if item['name'] in index_name:  # 类似 车身结构的 少量 会出现两次
                    for i in item['valueitems']:
                        before_value = car_content_dict[car_name_dict[i['specid']]][item['name']]
                        if before_value != i['value']:
                            if before_value in i['value']:
                                final = i['value']
                            elif i['value'] in before_value:
                                final = before_value
                            else:
                                final = [before_value, i['value']]
                            car_content_dict[car_name_dict[i['specid']]][item['name']] = final
                else:
                    index_name.append(item['name'])
                    for i in item['valueitems']:
                        if i['value'] !='':
                            car_content_dict[car_name_dict[i['specid']]][item['name']] = i['value']
                        else:
                            car_content_dict[car_name_dict[i['specid']]][item['name']] = [j['subname'] for j in i['sublist']]
                
        return car_content_dict, index_name

    def run(self):
        html = self.get_html()
        # 提取自调用函数
        js_list = re.findall(r'(function\([a-zA-Z]{2}.*?_\).*?)\)\(document\);', html)
        car_config_def = re.findall(self.config_pattern, html, re.S)[0]

        car_option_def = re.findall(self.option_pattern, html, re.S)[0]

        # 匹配到三段js分别对应baike，config，option参数选项，此处以option为示例
        
        for js in js_list:
            if "_config" in js:
                config_js = js
                car_info_config, car_name_dict_config = self.modify_run_js(config_js, car_config_def, 1)
                self.car_content_dict, config_index_name = self.get_car_content(car_info_config, car_name_dict_config, self.car_content_dict, 'config')
            elif "_option" in js:
                option_js = js
                car_info_option, _ = self.modify_run_js(option_js, car_option_def, 2)
                self.car_content_dict, option_index_name = self.get_car_content(car_info_option, car_name_dict_config, self.car_content_dict, 'option')
        
        df_car_content = pd.DataFrame.from_dict(self.car_content_dict)
        car_name = list(car_name_dict_config.values())[0]
        pd.DataFrame(df_car_content).to_excel('%s.xls'%(car_name))


if __name__ == '__main__':
    carHome = AutoHome()
    carHome.run()
