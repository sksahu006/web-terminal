FROM golang:1.22-alpine AS builder

WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/server main.go

FROM alpine:3.20

RUN echo "flag{unrestricted_upload_rce}" > /flag.txt \
    && mkdir -p /app/uploads

COPY --from=builder /out/server /app/server

EXPOSE 8000

WORKDIR /app
ENTRYPOINT ["/app/server"]
