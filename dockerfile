FROM python:3-alpine
MAINTAINER WuJian_Home
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 80
ENV cookies=none passkey=none only_free=1 only_hot=0 survival_time_limit=0 downloading_people_limit=0 hotword=none hot_or_free=0
CMD ["sh", "-c", "python3 main.py --cookies \"$cookies\" --passkey $passkey --only_free $only_free --only_hot $only_hot --survival_time_limit $survival_time_limit --downloading_people_limit $downloading_people_limit --hotword $hotword --hot_or_free $hot_or_free"]
