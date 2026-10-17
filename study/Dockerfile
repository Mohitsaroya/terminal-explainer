# Sandbox for user testing: a throwaway zsh with explain-term and a seeded practice folder.
#
#   docker build -f study/Dockerfile -t explain-study .
#   docker run --rm -it explain-study              # with explain-term
#   docker run --rm -it -e EXPLAIN_OFF=1 explain-study   # plain terminal (control)
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends zsh git less nano tree \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/zsh tester
COPY . /opt/explain-term
RUN pip install --no-cache-dir /opt/explain-term

USER tester
WORKDIR /home/tester
RUN bash /opt/explain-term/study/seed.sh /home/tester/practice \
 && echo 'source /opt/explain-term/hook/explain.zsh' >> ~/.zshrc \
 && echo 'cd ~/practice' >> ~/.zshrc

ENV EXPLAIN_LOG=/home/tester/explain-log.jsonl
CMD ["zsh"]
