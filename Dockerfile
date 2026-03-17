FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY app.py add_document.py ${LAMBDA_TASK_ROOT}

CMD ["app.handler"]
