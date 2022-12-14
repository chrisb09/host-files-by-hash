# syntax=docker/dockerfile:1

FROM tiangolo/uvicorn-gunicorn:python3.11

WORKDIR /

RUN mkdir /root/.ssh
RUN ssh-keyscan github.com >> /root/.ssh/known_hosts

RUN git clone https://github.com/chrisb09/thumbnail

WORKDIR thumbnail
RUN apt-get update
RUN apt-get install -y ffmpeg imagemagick curl libreoffice
RUN pip install unoserver
RUN python3 setup.py install --user

WORKDIR /python-docker


COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
