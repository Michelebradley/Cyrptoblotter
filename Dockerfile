FROM python:3

WORKDIR /app
ADD . /app

RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["python", "cryptoblotter.py", "—host = 0.0.0.0"]