import re
from flask import Flask, render_template, request, send_from_directory, Response
from flask_apscheduler import APScheduler
from bs4 import BeautifulSoup
import PyRSS2Gen

import datetime, time, os, cv2
import requests
import numpy as np
import argparse
import subprocess


# 端口 用户名 密码 passkey

def get_args():
    parser = argparse.ArgumentParser(description='PyTorch CNN Training on CIFAR-10')
    parser.add_argument('--user', type=str)
    parser.add_argument('--password', type=str)
    parser.add_argument('--passkey', type=str)
    parser.add_argument('--port', type=int, default=80)
    parser.add_argument('--hotword', type=str, default='')
    args = parser.parse_args()
    return args


args = get_args()
user = args.user
password = args.password
passkey = args.passkey
port = args.port
free = True
hot = True
other_rule = False
user_headers = {
    'User-Agent': 'Edg/87.0.4280.88',
}


def trans(torrent):
    title = torrent.select('a')[1]['title']
    link = 'https://pt.sjtu.edu.cn/{}&passkey={}'.format(torrent.select('a')[2]['href'], passkey)
    description = torrent.select('br')[0].text
    return PyRSS2Gen.RSSItem(title=title, link=link, description=description)


def get_number(torrent):
    tmp = torrent.select('tr>td')
    uploading = int(tmp[-4].text.replace(',', ''))
    downloading = int(tmp[-3].text.replace(',', ''))
    finished = int(tmp[-2].text.replace(',', ''))

    return uploading, downloading, finished


def get_number_flag(torrent):
    uploading, downloading, finished = get_number(torrent)  # 正在上传的人数，正在下载的人数，完成人数

    if downloading > 15:
        return True and other_rule
    if uploading < 15 and downloading > 5:
        return True and other_rule
    return False


def get_size_flag(torrent):
    string = str(torrent.select('tr>td')[-5].text)
    uploading, downloading, finished = get_number(torrent)
    if 'GB' in string:
        if float(string[:-2]) > 10 and downloading >= 2:  # 下载人数大于2 并且文件大小大于10GB
            return True and other_rule
    return False


def get_free_hot_flag(torrent):
    # 免费种子或者热门种子  
    return (('free_bg' in str(torrent)) and free) or (('hot' in str(torrent)) and hot)


def get_nums_signs_checkcode(i, keys, pattens):
    for idx in range(12):
        if abs(i * pattens[idx] - pattens[idx]).sum() == 0:
            return keys[idx] if keys[idx] != 'x' else '*'


def get_hot_word_flag(torrent):
    if args.hotword == '':
        return False
    hotwords = args.hotword.split(",")
    for hotword in hotwords:
        if hotword in str(torrent):
            return True
    return False


def login():
    # print('\r\rVisited  ', datetime.datetime.utcnow())
    login_url = 'https://pt.sjtu.edu.cn/takelogin.php'

    login_data = {
        'username': user,
        'password': password,
        'checkcode': 'XxXx'
    }
    session = requests.Session()
    session.trust_env = False
    response = session.get('https://pt.sjtu.edu.cn/login.php', headers=user_headers,  )
    if '验证码' in response.content.decode():
        print("Warning checkcode appears")
        # print(response.content.decode())
        soup = BeautifulSoup(response.content.decode(), features="html.parser")
        img_url = "https://pt.sjtu.edu.cn/" + soup.select('img')[-1].get("src")
        img = session.get(img_url, headers=user_headers,  ).content
        img = cv2.imdecode(np.frombuffer(img, np.uint8), cv2.IMREAD_GRAYSCALE)
        img = np.asarray(img, np.float32)
        img = (200 - img[9:19, 10:54]) / 200
        keys = [1, 2, 3, 4, 5, 6, 7, 8, 9, '+', 'x', '-']
        pattens = [np.load(('./patten/' + '{}.npy').format(key)) for key in keys]

        signs = [img[:, 0:8], img[:, 9:17], img[:, 18:26], img[:, 27:35], img[:, 36:44]]
        formula = [str(get_nums_signs_checkcode(sign, keys, pattens)) for sign in signs]
        ans = eval("".join(formula))
        login_data['checkcode'] = str(ans)
        # with open('./img.png', 'wb') as f:
        #     f.write(img)
    response = session.post(login_url, headers=user_headers, data=login_data,  )
    if '验证码' in response.content.decode():
        raise ImportError
    return session


def get_rss():
    # flash_config()
    global session, record_time
    if time.time() - record_time > 60 * 60:
        session = login()
        record_time = time.time()

    response = session.get('https://pt.sjtu.edu.cn/torrents.php', headers=user_headers,  )
    soup = BeautifulSoup(response.content.decode(), features="html.parser")
    if "验证码" in soup:
        print("Warning: checkcode appears, relogin")
        session = login()

    torrents = soup.select('.torrents>tr')[1:]

    items = []
    # print(len(torrents))
    for torrent in torrents:
        if get_number_flag(torrent) or get_size_flag(torrent) or get_free_hot_flag(torrent) or get_hot_word_flag(torrent):
            # print(get_number_flag(torrent) , get_size_flag(torrent), get_free_hot_flag(torrent))
            # print(torrent.select('a')[1]['title'], get_number(torrent))
            items.append(trans(torrent))

    rss = PyRSS2Gen.RSS2(title=user+'的RSS订阅, Hotword启动', link="http://127.0.0.1/{}".format(port), description=user+'的自定义RSS订阅', pubDate=datetime.datetime.utcnow(), items=items)
    return rss.to_xml()


class Config(object):
    # 添加定时任务
    JOBS = [
        {
            'id': 'job1',
            'func': 'rss:flash_both',
            'trigger': 'interval',
            'minutes': 5
        }
    ]
    SCHEDULER_API_ENABLED = True


def flash_both():
    subprocess.Popen('autoremove-torrents -c  ./config/config.yml', shell=True)


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'config/'


@app.route('/')
def rss():
    rss = get_rss()
    rss = rss.replace("iso-8859-1", "utf-8")
    r = Response(response=rss, status=200, mimetype="application/xml")
    r.headers["Content-Type"] = "text/xml; charset=utf-8"
    return r


@app.route('/upload')
def upload_file():
    return render_template('upload.html')


@app.route('/uploader', methods=['GET', 'POST'])
def uploader():
    if request.method == 'POST':
        f = request.files['file']
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'config.yml')
        print(file_path)
        f.save(file_path)

        return 'file uploaded successfully'

    else:

        return render_template('upload.html')


@app.route("/download", methods=['GET'])
def downloader():
    dirpath = app.config['UPLOAD_FOLDER']  # 这里是下在目录，从工程的根目录写起，比如你要下载static/js里面的js文件，这里就要写“static/js”
    return send_from_directory(dirpath, 'config.yml', as_attachment=True)  # as_attachment=True 一定要写，不然会变成打开，而不是下载


if __name__ == "__main__":
    print("begin")
    session = login()
    record_time = time.time()
    app.config.from_object(Config())
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()
    app.run(host='0.0.0.0', port=port)

# pyinstaller -F rss.py -w
