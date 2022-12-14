# syntax=docker/dockerfile:1

FROM tiangolo/uvicorn-gunicorn:python3.11

WORKDIR /python-docker

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

RUN ls / -la

RUN ls /python-docker -la

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
