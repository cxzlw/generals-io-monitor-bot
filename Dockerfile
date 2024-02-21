FROM python:3.9-buster
LABEL authors="cxzlw"

WORKDIR /app

RUN pip install poetry

COPY . .
RUN poetry install --no-dev

ENTRYPOINT ["poetry", "run", "python", "bot:bot"]
