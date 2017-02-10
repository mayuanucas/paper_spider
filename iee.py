#!usr/bin/env python
# -*- coding:utf-8 -*-
import re
import os
import time
import traceback
from common import base_dir, log_dir, ieee_updates_url, get_html_str,\
    init_dir
from util import get_phantomjs_page, get_database_connect, get_random_uniform


# 保存下载文件的目录
root_dir = base_dir + 'updates/ieee/'

# 程序运行日志文件
logfile = log_dir + 'update_ieee.txt'


# 处理1级页面
def handle_first_page(url):
    # 获得一级页面
    page_content = get_html_str(get_phantomjs_page(url))
    if page_content is None:
        print('page is none')
        return None
    options = page_content.find('select', id='updatesDate')
    if options is not None:
        update_date = options.find_next('option')['value']  #IEEE内容更新日期 eg:20170206
        if update_date is None:
            print('没有得到内容更新日期')
        elif update_date <= '20170202':
            print(update_date + '的内容已经更新')
        else:
            print('即将更新' + update_date +'的内容')
            ul = page_content.find('ul', class_='Browsing')
            if ul is not None:
                lis = ul.find_all_next('li', class_='noAbstract')
                urls = list(map(lambda li: 'http://ieeexplore.ieee.org/xpl/' + li.find_next('a').get('href'), lis))
                handle_second_page(urls)
    else:
        print('没有找到updatesDate')


# 处理2级页面
def handle_second_page(urls):
    links = list()
    for url in urls:
        print('2级页面：' + url)
        page_content = get_html_str(get_phantomjs_page(url))
        if page_content is None:
            print('2级页面' + url + '无法获取')
            return None
        ul = page_content.find('ul', class_='results')
        if ul is not None:
            divs = ul.find_all_next('div', class_='txt')
            for div in divs:
                temp = div.find_next('a', class_='art-abs-url')
                if temp is not None:
                    links.append('http://ieeexplore.ieee.org' + temp.get('href'))
        # 找到分页代码，获得分页总数，并向分页链接请求页面内容
        pagination = page_content.find('div', class_='pagination')
        if pagination is not None:
            a_list = pagination.select('a[aria-label^="Pagination Page"]')
            if a_list:
                pageNumber = a_list[-1].get_text().strip()
                if pageNumber is not None:
                    pageNumber = int(pageNumber)
                    url_list = list()
                    for number in range(2, pageNumber+1):
                        url_list.append(url + '&pageNumber=' + str(number))
                    for tmp_url in url_list:
                        page_content = get_html_str(get_phantomjs_page(tmp_url))
                        if page_content is None:
                            print('2级页面' + url + '无法获取')
                            return None
                        ul = page_content.find('ul', class_='results')
                        if ul is not None:
                            divs = ul.find_all_next('div', class_='txt')
                            for div in divs:
                                temp = div.find_next('a', class_='art-abs-url')
                                if temp is not None:
                                    links.append('http://ieeexplore.ieee.org' + temp.get('href'))
        else:
            print('没有找到分页代码' + url)
        break   # 先采集一个链接的数目
        time.sleep(get_random_uniform(begin=60.0, end=300.0))
    handle_third_page(links)    # 已采集到当前页面上的所有3级页面的链接


def handle_third_page(urls):
    print('链接总数为:' + str(len(urls)))
    for url in urls:
        print('3级页面:' + url)
        data_dict = dict()
        page_content = get_html_str(get_phantomjs_page(url))
        if page_content is None:
            print('3级页面无法获取')
            return None
        # 论文URL地址
        data_dict['url'] = url
        # 采集论文名
        if page_content.title is not None:
            data_dict['title'] = page_content.title.string
        # 采集论文关键词信息
        ul = page_content.find('ul', class_= 'doc-all-keywords-list')
        if ul is None:
            print('无法找到ul')
            return None
        spans = ul.find_all_next('span')
        keywords = list()
        for span in spans:
            temp = span.find_next('a', class_='ng-binding')
            if temp is not None:
                keywords.append(temp.get_text().strip())
        data_dict['keywords'] = keywords
        # 采集论文作者信息
        h2 = page_content.find('h2', text='Authors')
        if h2 is not None:
            div = h2.find_next_sibling('div', class_='ng-scope')
            if div is not None:
                temp = div.select('a[href^="/search/searchresult.jsp?searchWithin="]')
                if temp is not None:
                    authors_dict = dict()    # 保存多个作者信息到字典
                    for a in temp:
                        affiliation_dict = dict()
                        span = a.find_next('span', class_='ng-binding')
                        if span is not None:
                            author_name = span.get_text().strip()
                            tmp = a.parent.find_next_sibling('div', class_='ng-binding')
                            if tmp is not None:
                                affiliation = tmp.get_text().strip()
                                data_list = re.split(r',', affiliation)
                                affiliation_dict['affiliation'] = affiliation
                                affiliation_dict['affiliation_name'] = data_list[-2]
                                affiliation_dict['affiliation_country'] = data_list[-1]
                            authors_dict[author_name] = affiliation_dict
                    data_dict['author'] = authors_dict
        # 获取论文参考信息
        page_content = get_html_str(get_phantomjs_page(url + 'references?ctx=references'))
        if page_content is not None:
            h2 = page_content.find('h2', text='References')
            if h2 is not None:
                divs = h2.find_next_siblings('div', class_='reference-container ng-scope')
                references = list()
                for div in divs:
                    div_temp = div.find_next('div', class_='description ng-binding')
                    if div_temp:
                        references.append(div_temp.get_text().strip())
                data_dict['references'] = references
        else:
            print('获取论文references信息失败')
        # 获取论文被引用信息
        page_content = get_html_str(get_phantomjs_page(url + 'citations?anchor=anchor-paper-citations-ieee&ctx=citations'))
        if page_content is not None:
            # Cited in Papers - IEEE
            h2 = page_content.find('h2', text=re.compile(r'Cited in Papers - IEEE'))
            citations = list()
            if h2 is not None:
                divs = h2.find_next_siblings('div', class_='ng-scope')
                for div in divs:
                    div_temp = div.find_next('div', class_='description ng-binding')
                    if div_temp:
                        citations.append(div_temp.get_text().strip())
            # Cited in Papers - Other Publishers
            h2 = page_content.find('h2', text=re.compile(r'Cited in Papers - Other Publishers'))
            if h2 is not None:
                divs = h2.find_next_siblings('div', class_='ng-scope')
                for div in divs:
                    div_temp = div.find_next('div', class_='description ng-binding')
                    if div_temp:
                        citations.append(div_temp.get_text().strip())
            data_dict['citations'] = citations
        print(data_dict)

# 采集ieee更新的内容
def update_ieee(urls):
    for key, values in urls.items():
        if key == 'conferences':
            for url in values:
                handle_first_page(url)


def run_iee():
    init_dir(log_dir)
    init_dir(root_dir)
    with open(logfile, 'a+', encoding='utf-8') as f:
        f.write('update_ieee正常启动:%s' % (time.strftime('%Y.%m.%d %H:%M:%S')) + '\n')
    try:
        update_ieee(ieee_updates_url)
    except Exception as e:
        with open(logfile, 'a+', encoding='utf-8') as f:
            traceback.print_exc(file=f)
            f.write('update_ieee异常停止%s' % (time.strftime('%Y.%m.%d %H:%M:%S')) + str(e) + '\n\n')
    else:
        with open(logfile, 'a+', encoding='utf-8') as f:
            f.write('update_ieee正常停止:%s' % (time.strftime('%Y.%m.%d %H:%M:%S')) + '\n\n')


if __name__ == '__main__':
    # print(fun())
    # run_iee()
    # handle_second_page(['http://ieeexplore.ieee.org/xpl/tocresult.jsp?isnumber=7842910',])
    handle_third_page(['http://ieeexplore.ieee.org/document/7140733/',])