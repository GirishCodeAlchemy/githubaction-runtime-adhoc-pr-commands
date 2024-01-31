# FROM alpine:latest
FROM python:3.10-slim

LABEL version="1.0.0"
LABEL repository="https://github.com/GirishCodeAlchemy/githubaction-runtime-adhoc-pr-commands.git"
LABEL homepage="https://github.com/GirishCodeAlchemy/githubaction-runtime-adhoc-pr-commands"
LABEL maintainer="GirishCodeAlchemy"
LABEL "com.github.actions.name"="Runtime Githubaction Adhoc PR commands"
LABEL "com.github.actions.description"="Run the adhoc commands on the runtime using Githubaction on the PR"
LABEL "com.github.actions.icon"="git-pull-request"
LABEL "com.github.actions.color"="gray-dark"


# Install packages
# RUN apk --no-cache add jq bash curl git git-lfs

# Install git
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    jq \
    curl \
    git-lfs \
    wget \
    requests \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy scripts
COPY scripts /app/

RUN chmod +x /app/entrypoint.sh

# ENTRYPOINT ["/app/entrypoint.sh"]
ENTRYPOINT ["python3","/app/alchemy.py"]
