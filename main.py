import requests
import argparse
import json
from bs4 import BeautifulSoup
import PyRSS2Gen
import re
import datetime
from flask import Flask, Response

def get_hot_word_flag(torrent):
    if args.hotword == '':
        return False
    hotwords = args.hotword.split(",")
    for hotword in hotwords:
        if hotword in str(torrent):
            return True
    return False


def time_to_minutes(time_str):

    # Define a dictionary to hold the conversion values for each unit
    conversion = {'年': 525600,"月":1440*30, '天': 1440, '时': 60, '分': 1}

    # Use regular expressions to find all occurrences of time units and their values
    time_components = re.findall(r'(\d+)([年月天时分])', time_str)

    # Convert and sum up the minutes
    total_minutes = sum(int(value) * conversion[unit] for value, unit in time_components)

    return total_minutes

def parse_cookies(cookies_str):
    cookies = {}
    for cookie in cookies_str.split('; '):
        key, value = cookie.split('=', 1)
        cookies[key] = value
    return cookies



def get_torrent_info_putao(table_row, passkey, args):
    free_flag = "free_bg" in str(table_row)

    free_time = None

    hot_flag = bool(table_row.find('font', class_='hot'))


    survival_time = table_row.select("td.rowfollow span.nobr")[1].text

    name = table_row.select("td.embedded  a b" )[0].text

    download_href = "https://pt.sjtu.edu.cn/" + table_row.select("td.embedded  a " )[2].get("href")
    download_href =  download_href + "&passkey={}".format(passkey)

    td_rowfollow = table_row.select("td.rowfollow")

    size = td_rowfollow[-5].text

    uploading_people = td_rowfollow[-4].text

    downloading_people = td_rowfollow[-3].text

    finished_people = td_rowfollow[-2].text

    description = table_row.select("td.embedded" )[0].text

    comments = "是否热门:{}\t是否免费:{}\t免费时间:{}\t存活时间:{}\t大小:{}\t上传人数:{}\t下载人数:{}\t完成人数:{}".format(
        hot_flag, free_flag, free_time, survival_time, size, uploading_people, downloading_people, finished_people)

    rss_item = PyRSS2Gen.RSSItem(title=name, link=download_href, description=description, comments=comments)

    if get_hot_word_flag(table_row):
        return rss_item

    if (args.only_free and not free_flag) or (args.only_hot and not hot_flag) or (args.survival_time_limit > 0 and time_to_minutes(survival_time) > args.survival_time_limit):
        return None

    if args.hot_or_free and (not hot_flag and not free_flag):
        return None

    return rss_item



def get_torrent_putao(args, session, headers):
    cookies = parse_cookies(args.cookies)
    for name, value in cookies.items():
        session.cookies.set(name, value)

    proxies= {}
    response = session.get('https://pt.sjtu.edu.cn/torrents.php',
                           headers=headers,
                           proxies=proxies)
    soup = BeautifulSoup(response.text, 'html.parser')
    table_rows = soup.select('table.torrents > tr')[1:]

    items = []
    for table_row in table_rows:
        rss_item = get_torrent_info_putao(table_row, args.passkey, args)
        if rss_item:
            items.append(rss_item)

    return items


user_headers = {
    'User-Agent': 'Edg/87.0.4280.88',
}

parser = argparse.ArgumentParser(description='Login to a website using cookies from command line.')
parser.add_argument('--cookies',type=str)
parser.add_argument("--passkey", type=str)
parser.add_argument("--only_free", type=int, default=0)
parser.add_argument("--only_hot", type=int, default=0)
parser.add_argument("--hot_or_free", type=int, default=1)
parser.add_argument("--survival_time_limit", default=0, help="默认单位为分", type=int)
parser.add_argument("--port", default=80, type=int)
parser.add_argument("--downloading_people_limit", default=0, help="默认单位为人", type=int)
parser.add_argument("--hotword", type=str, default="")
args = parser.parse_args()
print(args)
session = requests.Session()
# rss_items = get_torrent_putao(args, session, user_headers)

app = Flask(__name__)

@app.route('/')
def rss():
    rss_items = get_torrent_putao(args, session, user_headers)

    rss = PyRSS2Gen.RSS2(title='Coatsocold的HDKylin RSS订阅', link="http://127.0.0.1:{}".format(args.port), description='自定义RSS订阅', pubDate=datetime.datetime.utcnow(), items=rss_items)
    rss = rss.to_xml()
    rss = rss.replace("iso-8859-1", "utf-8")
    r = Response(response=rss, status=200, mimetype="application/xml")
    r.headers["Content-Type"] = "text/xml; charset=utf-8"
    return r

app.run(host='0.0.0.0', port=args.port)

