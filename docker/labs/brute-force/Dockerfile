FROM golang:1.22-alpine AS builder

WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/server main.go

FROM scratch

COPY --from=builder /out/server /server

EXPOSE 8000

ENTRYPOINT ["/server"]
