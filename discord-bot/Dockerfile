FROM python:3-slim

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN apt-get update && apt-get install -y gcc
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "./bot.py" ]