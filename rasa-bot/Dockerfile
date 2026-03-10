FROM rasa/rasa:3.6.0

WORKDIR /app

COPY . /app

RUN rasa train

CMD ["rasa","run","--enable-api","--cors","*","--port","$PORT"]