FROM python:3.9-slim

WORKDIR /bot

COPY requirements.txt /bot/
RUN pip install -r requirements.txt

COPY . /bot

CMD ["python", "main.py"]