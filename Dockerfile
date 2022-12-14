# syntax=docker/dockerfile:1

FROM tiangolo/uvicorn-gunicorn:python3.11

RUN cd / && git clone git@github.com:chrisb09/thumbnail.git && cd thumbnail && python3 setup.py install --user

WORKDIR /python-docker

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]