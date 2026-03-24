FROM python:3.10

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

RUN rasa train

EXPOSE 5005

CMD ["rasa","run","--enable-api","--cors","*","--port","5005"]
