FROM python:3.9-buster
LABEL authors="cxzlw"

RUN pip install poetry

COPY . .
RUN poetry install --no-dev

ENTRYPOINT ["poetry", "run", "hypercorn", "bot:bot"]
