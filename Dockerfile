FROM ubuntu:latest
LABEL authors="Carter"

ENTRYPOINT ["top", "-b"]