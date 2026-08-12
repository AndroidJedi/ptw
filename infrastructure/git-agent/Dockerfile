FROM alpine:3.22
RUN apk add --no-cache openssh-client su-exec \
    && addgroup -S -g 10001 ptw \
    && adduser -S -u 10001 -G ptw ptw
COPY infrastructure/git-agent/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
