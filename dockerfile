FROM python:3
MAINTAINER WuJian_Home
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 80
ENV user=none password=none passkey=none
CMD ["sh", "-c", "python3 rss.py --user $user --password $password --passkey $passkey"]
