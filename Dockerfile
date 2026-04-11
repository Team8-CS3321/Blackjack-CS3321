FROM ubuntu:22.04
LABEL authors="Carter"

COPY . .

RUN uv sync

EXPOSE 3000

ENTRYPOINT ["top", "-b"]