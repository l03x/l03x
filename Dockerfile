FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY update-life.sh /usr/local/bin/update-life
RUN chmod +x /usr/local/bin/update-life

# no root needed: the job only clones to /tmp and pushes
RUN useradd --create-home life
USER life

ENTRYPOINT ["update-life"]