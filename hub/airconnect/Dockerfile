FROM alpine:3.20

RUN apk add --no-cache ca-certificates

WORKDIR /opt/airconnect
COPY upstream/aircast-linux-x86_64-static /usr/local/bin/aircast
RUN chmod +x /usr/local/bin/aircast

ENTRYPOINT ["/usr/local/bin/aircast"]
CMD ["-Z"]
