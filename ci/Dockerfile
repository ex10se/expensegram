FROM python:3.9-alpine

COPY --chown=www-data:www-data requirements.txt /var/app/requirements.txt
RUN cd /var/app/ && pip install -r requirements.txt

VOLUME /var/app/
EXPOSE 8000
WORKDIR /var/app/

COPY --chown=www-data:www-data ci/entrypoint.sh /entrypoint.sh

CMD ["/entrypoint.sh"]
