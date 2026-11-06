FROM ghcr.io/home-assistant/base:3.24

RUN apk add --no-cache python3
COPY server.py dashboard.html app.css app.js /opt/quietcool/
COPY run.sh /run.sh
RUN chmod +x /run.sh
WORKDIR /opt/quietcool
CMD [ "/run.sh" ]
