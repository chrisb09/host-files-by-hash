# syntax=docker/dockerfile:1

FROM tiangolo/uvicorn-gunicorn:python3.11

RUN apt-get update
RUN apt-get install -y ffmpeg imagemagick

WORKDIR /host-files-by-hash

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 7222

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
